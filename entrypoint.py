import os
from flask import jsonify, send_from_directory, session, request, Response
from server import app
import meta_sync_flow
import onesignal_flow
from app import get_db, read_logs, write_logs, require_admin


meta_sync_flow.install(
    app,
    get_db=get_db,
    read_logs=read_logs,
    write_logs=write_logs,
)

onesignal_flow.install(
    app,
    get_db=get_db,
    require_admin=require_admin,
)


@app.before_request
def mx_meta_module_response():
    if request.path.rstrip('/') != '/modules/meta-ads.html':
        return None
    p = os.path.join('.', 'modules', 'meta-ads.html')
    if not os.path.isfile(p):
        return None
    with open(p, 'r', encoding='utf-8') as f:
        html = f.read()
    try:
        html = meta_sync_flow._inject_meta_module(html)
    except Exception as e:
        print('mx meta module:', e)
    return Response(html, mimetype='text/html; charset=utf-8')


@app.after_request
def mx_notification_menu_injection(response):
    """Inject the OneSignal menu loader into the panel shell."""
    try:
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
            return response
        response.direct_passthrough = False
        html = response.get_data(as_text=True)
        if 'id="mainContent"' not in html or '/modules/bildirim-menu.js' in html:
            return response
        tag = '<script src="/modules/bildirim-menu.js?v=20260711-2"></script>'
        if '</body>' in html:
            html = html.replace('</body>', tag + '</body>')
        else:
            html += tag
        response.set_data(html)
        response.headers['Content-Length'] = str(len(response.get_data()))
    except Exception as e:
        print('Bildirim menü injection:', e)
    return response


_RESERVED_PREFIXES = (
    'api',
    'auth',
    'admin',
    'ga4',
    'gads',
    'logs',
    'psi',
    'claude',
    'proxy-xml',
    'trendyol',
    'onesignal',
)


@app.route('/<path:path>')
def spa_fallback(path):
    """Serve existing files or fall back to the panel shell for frontend routes."""
    clean_path = (path or '').strip('/')
    first_part = clean_path.split('/', 1)[0]

    if first_part in _RESERVED_PREFIXES:
        return jsonify({'error': 'Endpoint bulunamadı'}), 404

    if clean_path:
        root_file = os.path.join('.', clean_path)
        if os.path.isfile(root_file):
            directory = os.path.dirname(clean_path) or '.'
            filename = os.path.basename(clean_path)
            return send_from_directory(directory, filename)

    if not session.get('user_email'):
        return send_from_directory('.', 'login.html') if os.path.exists('login.html') else send_from_directory('.', 'index.html')

    return send_from_directory('.', 'index.html')