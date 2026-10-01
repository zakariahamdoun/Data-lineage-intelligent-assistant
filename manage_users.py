"""Run locally on the application server; never exposed in Streamlit."""
import argparse
import getpass
from pathlib import Path
import sqlite3
from auth_store import connection, initialize, add_user, set_active, reset_password


def main():
    parser=argparse.ArgumentParser(description='Gestion locale des utilisateurs autorisés')
    parser.add_argument('--db',type=Path,default=Path(__file__).resolve().with_name('app_users.db'))
    parser.add_argument('action',choices=['add','enable','disable','password','list'])
    parser.add_argument('username',nargs='?')
    args=parser.parse_args()
    if args.action!='list' and not args.username:parser.error('Un matricule est requis.')
    initialize(args.db)
    try:
        if args.action=='list':
            with connection(args.db) as conn:
                for username,active in conn.execute('SELECT username,is_active FROM users ORDER BY username'):
                    print(username+(' : actif' if active else ' : désactivé'))
            return
        if args.action in ('add','password'):
            password=getpass.getpass('Mot de passe (12 caractères minimum) : ')
            if password!=getpass.getpass('Confirmer le mot de passe : '):
                raise ValueError('Les mots de passe diffèrent.')
            if args.action=='add':add_user(args.db,args.username,password)
            else:reset_password(args.db,args.username,password)
        else:set_active(args.db,args.username,args.action=='enable')
        print('Compte mis à jour.')
    except ValueError as error:
        parser.exit(1,str(error)+'\n')


if __name__=='__main__':main()
