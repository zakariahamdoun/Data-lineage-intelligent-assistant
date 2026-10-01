"""Presentation only for the Administration page."""
from html import escape


ADMIN_CSS = """
<style>
.st-key-admin_workspace {color:#263143;}
.st-key-admin_workspace .admin-eyebrow {color:#a44a12;font-size:11px;font-weight:750;letter-spacing:2px;margin:8px 0;}
.st-key-admin_workspace h1 {font-size:38px;letter-spacing:-1.2px;padding:0 0 8px;}
.st-key-admin_workspace .admin-subtitle {color:#717784;margin:0 0 20px;}
.st-key-admin_workspace button {border-radius:9px;min-height:42px;font-weight:600;box-shadow:none;}
.st-key-admin_workspace button[kind="primary"] {background:#c6530b;border-color:#c6530b;color:white;}
.st-key-admin_workspace button[kind="primary"]:hover {background:#a94307;border-color:#a94307;}
.st-key-admin_workspace button:focus-visible {outline:3px solid #efb47c;outline-offset:2px;}
.st-key-admin_workspace button:disabled {opacity:.45;}
.st-key-admin_table,.st-key-admin_details {background:white;border:1px solid #e5e7eb;border-radius:16px;padding:24px;box-shadow:0 4px 18px #24324706;}
.st-key-admin_workspace h3 {font-size:20px;padding-top:0;}
.st-key-admin_table_heading {background:#f7f8fa;border-radius:8px;padding:12px 14px;color:#737b88;font-size:13px;font-weight:650;}
.st-key-admin_workspace [class*="st-key-admin_user_row_"] {border-bottom:1px solid #edf0f3;padding:14px;}
.st-key-admin_workspace .admin-person {display:flex;align-items:center;gap:12px;overflow-wrap:anywhere;font-weight:650;}
.st-key-admin_workspace .admin-avatar {display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;flex-shrink:0;border-radius:10px;background:#fff1e5;color:#a9470b;font-size:14px;}
.st-key-admin_workspace .admin-status {display:inline-flex;align-items:center;gap:7px;padding:5px 10px;border-radius:20px;font-size:13px;font-weight:650;white-space:nowrap;}
.st-key-admin_workspace .admin-status.active {background:#edf8f1;color:#227448;}
.st-key-admin_workspace .admin-status.inactive {background:#fdf0ef;color:#b03232;}
.st-key-admin_workspace .admin-dot {height:7px;width:7px;border-radius:50%;background:currentColor;}
.st-key-admin_workspace .admin-protected {display:inline-block;background:#f0f1f3;color:#666e79;border:1px solid #e3e5e9;border-radius:6px;padding:7px 11px;font-size:12px;}
.st-key-admin_workspace .admin-date {color:#697281;font-size:14px;overflow-wrap:anywhere;}
.st-key-admin_workspace .admin-label {color:#727987;font-size:12px;margin-bottom:9px;}
.st-key-admin_workspace .admin-value {font-weight:650;overflow-wrap:anywhere;}
.st-key-admin_workspace [class*="st-key-admin_row_delete_"] button {color:#b03232;border-color:#eccbcb;background:#fff8f7;}
.st-key-admin_workspace .st-key-admin_delete_user button {background:#ba3737;border-color:#ba3737;color:white;}
.st-key-admin_workspace .admin-information {display:flex;gap:14px;border:1px solid #f3d8bd;background:#fff7ed;color:#805326;padding:20px 24px;border-radius:12px;margin-top:8px;font-size:14px;line-height:1.7;}
.st-key-admin_workspace .admin-info-icon {font-size:21px;line-height:1.4;}
.st-key-admin_workspace .access-requests-breadcrumb {color:#8a919d;font-size:12px;font-weight:650;margin:28px 0 7px;}
.st-key-admin_workspace .access-requests-breadcrumb span {color:#a44a12;}
.st-key-admin_workspace .access-requests-title-row {display:flex;align-items:center;gap:11px;margin:0 0 3px;}
.st-key-admin_workspace .access-requests-title-row h2 {font-size:27px;letter-spacing:-.7px;margin:0;color:#263143;}
.st-key-admin_workspace .access-requests-subtitle {color:#7d8490;font-size:13px;margin:0;}
.st-key-admin_workspace [class*="st-key-admin_access_request_"] {background:#fff;border:1px solid #e7e9ed;border-radius:15px;padding:13px 15px 11px;margin:9px 0;box-shadow:0 4px 18px rgba(36,50,71,.035);}
.st-key-admin_workspace .access-request-header {display:grid;grid-template-columns:44px minmax(165px,1.45fr) minmax(105px,.75fr) minmax(125px,1fr) minmax(125px,1fr) minmax(120px,.9fr);gap:14px;align-items:center;}
.st-key-admin_workspace .access-request-avatar {display:grid;place-items:center;width:40px;height:40px;border-radius:50%;background:#fff0e4;color:#a9470b;font-size:13px;font-weight:800;}
.st-key-admin_workspace .access-request-person {min-width:0;}
.st-key-admin_workspace .access-request-name {color:#263143;font-size:14px;font-weight:760;line-height:1.25;overflow-wrap:anywhere;}
.st-key-admin_workspace .access-request-email {color:#7d8490;font-size:12px;margin-top:3px;overflow-wrap:anywhere;}
.st-key-admin_workspace .access-request-meta {min-width:0;color:#5e6878;font-size:12px;line-height:1.35;overflow-wrap:anywhere;}
.st-key-admin_workspace .access-request-meta-label {display:block;color:#9aa1ab;font-size:10px;font-weight:750;letter-spacing:.04em;text-transform:uppercase;margin-bottom:2px;}
.st-key-admin_workspace .access-request-pending {display:inline-flex;align-items:center;border-radius:999px;background:#d65a16;color:#fff;padding:3px 7px;margin-left:6px;font-size:10px;font-weight:800;letter-spacing:.06em;vertical-align:2px;}
.st-key-admin_workspace .access-request-actions {display:grid;gap:6px;}
.st-key-admin_workspace [class*="st-key-access_request_accept_"] button,.st-key-admin_workspace [class*="st-key-access_request_reject_"] button,.st-key-admin_workspace [class*="st-key-access_request_toggle_"] button {min-height:31px;padding:0 10px;font-size:12px;border-radius:8px;}
.st-key-admin_workspace [class*="st-key-access_request_reject_"] button {color:#b03232;border-color:#eccbcb;background:#fff8f7;}
.st-key-admin_workspace [class*="st-key-access_request_toggle_"] button {color:#7a6570;border-color:transparent;background:transparent;padding:0 3px;}
.st-key-admin_workspace .access-request-detail {border-top:1px solid #edf0f3;margin-top:11px;padding-top:12px;}
.st-key-admin_workspace .access-request-reason {border:1px solid #f0dfce;background:#fff9f3;border-radius:11px;padding:12px 14px;color:#5d5149;font-size:13px;line-height:1.55;margin:0 0 12px;overflow-wrap:anywhere;}
.st-key-admin_workspace .access-request-reason-title {color:#9b551f;font-size:12px;font-weight:800;margin-bottom:5px;}
.st-key-admin_workspace .access-request-detail-note {color:#7d8490;font-size:12px;margin:0 0 10px;}
.st-key-admin_workspace .access-request-footer {color:#a44a12;font-size:12px;font-weight:650;}
.st-key-admin_workspace .admin-request-heading {display:flex;align-items:center;gap:10px;margin:22px 0 4px;}
.st-key-admin_workspace .admin-request-heading h3 {margin:0;padding:0;}
.st-key-admin_workspace .admin-request-count {display:inline-flex;align-items:center;border-radius:999px;background:#d65a16;color:#fff;padding:4px 9px;font-size:11px;font-weight:750;line-height:1;white-space:nowrap;}
@media(max-width:760px) {
 .st-key-admin_table,.st-key-admin_details {padding:16px;}
 .st-key-admin_workspace h1 {font-size:30px;}
 .st-key-admin_table_heading {display:none;}
 .st-key-admin_workspace .access-request-header {grid-template-columns:44px minmax(0,1fr) minmax(0,1fr);gap:10px;}
}
</style>
"""


def status_markup(active):
    state, label = ('active', 'Actif') if active else ('inactive', 'Désactivé')
    return f'<span class="admin-status {state}"><span class="admin-dot"></span>{label}</span>'


def person_markup(username):
    return (f'<div class="admin-person"><span class="admin-avatar">{escape(username[:1].upper())}</span>'
            f'<span>{escape(username)}</span></div>')
