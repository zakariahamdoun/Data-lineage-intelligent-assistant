"""Local account storage shared by the login page and administrator CLI."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import unicodedata
from contextlib import closing, contextmanager
from pathlib import Path

ITERATIONS = 600_000
INCORRECT = 'Matricule ou mot de passe incorrect.'
DISABLED = "Votre accès est désactivé. Contactez l'administrateur."


@contextmanager
def connection(path):
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            yield conn


def _ensure_access_requests_table(conn):
    """Create the access-request storage and its pending-request safeguards."""
    conn.execute("""CREATE TABLE IF NOT EXISTS access_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT NOT NULL,
        email TEXT NOT NULL,
        matricule TEXT NOT NULL,
        department TEXT NOT NULL,
        job_title TEXT NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        processed_at TEXT)""")
    columns={row[1] for row in conn.execute('PRAGMA table_info(access_requests)')}
    # Database created by earlier versions: keep its requests and promote the
    # former requested identifier to the explicit matricule field.
    if 'matricule' not in columns:
        conn.execute('ALTER TABLE access_requests ADD COLUMN matricule TEXT')
        conn.execute('UPDATE access_requests SET matricule=username WHERE matricule IS NULL')
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS access_requests_pending_email "
                 "ON access_requests(email COLLATE NOCASE) WHERE status='pending'")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS access_requests_pending_matricule "
                 "ON access_requests(matricule COLLATE NOCASE) WHERE status='pending'")


def initialize(path, primary_admin='admin'):
    with connection(path) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users(
            username TEXT PRIMARY KEY, salt TEXT NOT NULL, password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER NOT NULL DEFAULT 0, password_iterations INTEGER NOT NULL DEFAULT 600000)""")
        columns={row[1] for row in conn.execute('PRAGMA table_info(users)')}
        if 'is_active' not in columns:
            conn.execute('ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 0')
            # Old self-service accounts have no evidence of administrator approval.
            conn.execute("UPDATE users SET is_active=1 WHERE username=? AND role='admin'",(primary_admin,))
        if 'password_iterations' not in columns:
            conn.execute('ALTER TABLE users ADD COLUMN password_iterations INTEGER NOT NULL DEFAULT 200000')
        if 'must_change_password' not in columns:
            conn.execute('ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0')
        _ensure_access_requests_table(conn)
        conn.execute("UPDATE users SET role='admin' WHERE username=? AND role!='admin'",(primary_admin,))
        conn.execute("UPDATE users SET role='user' WHERE username!=? AND role!='user'",(primary_admin,))


def password_hash(password, salt=None, iterations=ITERATIONS):
    salt=secrets.token_bytes(16) if salt is None else salt
    digest=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,iterations)
    return salt.hex(),digest.hex()


def clean_username(username):
    """Preserve display case, but discard surrounding spaces and invisible format marks."""
    return ''.join(c for c in unicodedata.normalize('NFKC',username)
                   if unicodedata.category(c)!='Cf').strip()


def username_key(username):
    return clean_username(username).casefold()


def user_exists(username, path=None, *, conn=None, debug=False):
    """Return a boolean, using the same connection as insertion when supplied."""
    if conn is None:
        path=Path(__file__).resolve().with_name('app_users.db') if path is None else path
        with connection(path) as opened:
            return user_exists(username,conn=opened,debug=debug)
    conn.create_function('username_key',1,username_key,deterministic=True)
    row=conn.execute('SELECT 1 FROM users WHERE username_key(username)=? LIMIT 1',
                     (username_key(username),)).fetchone()
    if debug:
        print('USERNAME TEST =',repr(username))
        print('FETCHONE RAW =',repr(row))
        print('USER EXISTS RESULT =',row is not None)
    return row is not None


def authenticate(path, username, password):
    with connection(path) as conn:
        conn.row_factory=sqlite3.Row
        row=conn.execute('SELECT * FROM users WHERE username=?',(clean_username(username),)).fetchone()
        if row is None:
            password_hash(password)  # Do comparable work for an unknown identifier.
            return None,INCORRECT
        _,candidate=password_hash(password,bytes.fromhex(row['salt']),row['password_iterations'])
        if not hmac.compare_digest(candidate,row['password_hash']):return None,INCORRECT
        if not row['is_active']:return None,DISABLED
        if row['password_iterations']<ITERATIONS:
            salt,digest=password_hash(password)
            conn.execute('UPDATE users SET salt=?,password_hash=?,password_iterations=? WHERE username=?',
                         (salt,digest,ITERATIONS,row['username']))
        return {'username':row['username'],'role':row['role']},None


def _insert_user(conn, username, password, primary_admin='admin', active=True):
    """Insert a user on an already locked transaction using the existing password hash."""
    username=clean_username(username)
    if len(username)<3:raise ValueError('Matricule : 3 caractères minimum.')
    if len(password)<12:raise ValueError('Mot de passe : 12 caractères minimum.')
    salt,digest=password_hash(password)
    if user_exists(username,conn=conn):
        raise ValueError('Ce matricule existe déjà.')
    try:
        conn.execute('INSERT INTO users(username,salt,password_hash,role,is_active,password_iterations,must_change_password,created_at) VALUES(?,?,?,?,?,?,1,CURRENT_TIMESTAMP)',
                     (username,salt,digest,'admin' if username==primary_admin else 'user',int(active),ITERATIONS))
    except sqlite3.IntegrityError as error:
        if str(error)=='UNIQUE constraint failed: users.username':
            raise ValueError('Ce matricule existe déjà.') from error
        raise


def add_user(path, username, password, primary_admin='admin', active=True):
    with connection(path) as conn:
        # Serialize duplicate checking and insertion, including concurrent requests.
        conn.execute('BEGIN IMMEDIATE')
        _insert_user(conn, username, password, primary_admin, active)


EMAIL_PATTERN=re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def submit_access_request(path, fullname, email, matricule, department, job_title, reason):
    """Validate and store a new access request in the local users database."""
    fullname, email=fullname.strip(), email.strip().lower()
    matricule=clean_username(matricule)
    department, job_title, reason=department.strip(), job_title.strip(), reason.strip()
    if not all((fullname,email,matricule,department,job_title,reason)):
        return False,'Tous les champs sont obligatoires.'
    if not EMAIL_PATTERN.fullmatch(email):
        return False,'Adresse e-mail professionnelle invalide.'
    if len(matricule)<3:
        return False,'Matricule : 3 caractères minimum.'
    if len(reason)<10:
        return False,'Le motif doit contenir au moins 10 caractères.'
    with connection(path) as conn:
        _ensure_access_requests_table(conn)
        conn.execute('BEGIN IMMEDIATE')
        if user_exists(matricule,conn=conn):
            return False,'Ce matricule est déjà utilisé.'
        duplicate=conn.execute("""SELECT 1 FROM access_requests
                                  WHERE status='pending' AND (email=? COLLATE NOCASE OR matricule=? COLLATE NOCASE)
                                  LIMIT 1""",(email,matricule)).fetchone()
        if duplicate:
            return False,'Une demande est déjà en attente pour cet e-mail ou ce matricule.'
        try:
            request_columns={row[1] for row in conn.execute('PRAGMA table_info(access_requests)')}
            if 'username' in request_columns:  # compatible with the pre-matricule table
                conn.execute("""INSERT INTO access_requests
                    (fullname,email,username,matricule,department,job_title,reason,status)
                    VALUES(?,?,?,?,?,?,?,'pending')""",
                    (fullname,email,matricule,matricule,department,job_title,reason))
            else:
                conn.execute("""INSERT INTO access_requests
                    (fullname,email,matricule,department,job_title,reason,status)
                    VALUES(?,?,?,?,?,?,'pending')""",
                    (fullname,email,matricule,department,job_title,reason))
        except sqlite3.IntegrityError as error:
            return False,'Une demande est déjà en attente pour cet e-mail ou ce matricule.'
    return True,'Votre demande d’accès a bien été transmise à l’administrateur.'


def access_requests(path, status=None):
    with connection(path) as conn:
        conn.row_factory=sqlite3.Row
        if status:
            rows=conn.execute('SELECT * FROM access_requests WHERE status=? ORDER BY created_at DESC, id DESC',(status,)).fetchall()
        else:
            rows=conn.execute('SELECT * FROM access_requests ORDER BY created_at DESC, id DESC').fetchall()
        return [dict(row) for row in rows]


def pending_access_requests_count(path):
    """Return the single source-of-truth count used by access-request badges."""
    with connection(path) as conn:
        _ensure_access_requests_table(conn)
        return int(conn.execute("SELECT COUNT(*) FROM access_requests WHERE status='pending'").fetchone()[0])


def approve_access_request(path, request_id, temporary_password, primary_admin='admin'):
    """Create an active user and approve one pending request as one transaction."""
    with connection(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.row_factory=sqlite3.Row
        request=conn.execute("SELECT * FROM access_requests WHERE id=? AND status='pending'",(request_id,)).fetchone()
        if not request:
            raise ValueError('Cette demande a déjà été traitée ou est introuvable.')
        _insert_user(conn, request['matricule'], temporary_password, primary_admin, True)
        updated=conn.execute("""UPDATE access_requests SET status='approved', processed_at=CURRENT_TIMESTAMP
                              WHERE id=? AND status='pending'""",(request_id,))
        if not updated.rowcount:
            raise ValueError('Cette demande a déjà été traitée ou est introuvable.')


def reject_access_request(path, request_id):
    with connection(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        updated=conn.execute("""UPDATE access_requests SET status='rejected', processed_at=CURRENT_TIMESTAMP
                              WHERE id=? AND status='pending'""",(request_id,))
        if not updated.rowcount:
            raise ValueError('Cette demande a déjà été traitée ou est introuvable.')


def access_request(path, request_id):
    with connection(path) as conn:
        conn.row_factory=sqlite3.Row
        row=conn.execute('SELECT * FROM access_requests WHERE id=?',(request_id,)).fetchone()
        return dict(row) if row else None


def set_active(path, username, enabled, primary_admin='admin'):
    if username==primary_admin and not enabled:raise ValueError('Le compte administrateur principal ne peut pas être désactivé.')
    with connection(path) as conn:
        result=conn.execute('UPDATE users SET is_active=? WHERE username=?',(int(enabled),username))
        if not result.rowcount:raise ValueError('Identifiant introuvable.')


def reset_password(path, username, password):
    if len(password)<12:raise ValueError('Mot de passe : 12 caractères minimum.')
    salt,digest=password_hash(password)
    with connection(path) as conn:
        result=conn.execute('UPDATE users SET salt=?,password_hash=?,password_iterations=?,must_change_password=1 WHERE username=?',
                            (salt,digest,ITERATIONS,username))
        if not result.rowcount:raise ValueError('Identifiant introuvable.')


def account_state(username, path=None):
    """Read the existing account; default to the database beside this module."""
    path=Path(__file__).resolve().with_name('app_users.db') if path is None else path
    with connection(path) as conn:
        conn.row_factory=sqlite3.Row
        row=conn.execute('SELECT username,role,is_active,must_change_password FROM users WHERE username=?',(username.strip(),)).fetchone()
        return dict(row) if row else None


def change_password(path,username,current,new,confirmation):
    if new!=confirmation:raise ValueError('Les nouveaux mots de passe ne sont pas identiques.')
    if len(new)<12:raise ValueError('Mot de passe : 12 caractères minimum.')
    if current==new:raise ValueError('Le nouveau mot de passe doit être différent du mot de passe actuel.')
    with connection(path) as conn:
        conn.row_factory=sqlite3.Row
        row=conn.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
        if not row:raise ValueError(INCORRECT)
        _,digest=password_hash(current,bytes.fromhex(row['salt']),row['password_iterations'])
        if not hmac.compare_digest(digest,row['password_hash']):raise ValueError('Mot de passe actuel incorrect.')
        if not row['is_active']:raise ValueError(DISABLED)
        salt,digest=password_hash(new)
        result=conn.execute('UPDATE users SET salt=?,password_hash=?,password_iterations=?,must_change_password=0 '
                            'WHERE username=? AND password_hash=? AND is_active=1',
                            (salt,digest,ITERATIONS,username,row['password_hash']))
        if not result.rowcount:raise ValueError('Le compte a été modifié. Reconnectez-vous.')
        return {'username':row['username'],'role':row['role']}
