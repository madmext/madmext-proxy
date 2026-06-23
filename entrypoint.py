import os
from flask import jsonify, send_from_directory, session
from server import app


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
)


@app.route('/<path:path>')
def spa_fallback(path):
    """Serve existing files or fall back to the panel shell for frontend routes.

    This prevents Railway/Flask from returning 404 when a React/Vite route such
    as /dosyalar, /kampanyalar, /analitik or any future panel page is opened
    directly or refreshed in the browser.
    """
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
