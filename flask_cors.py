"""Local lightweight flask_cors shim for Madmext Railway runtime.

Keeps the existing CORS(app, supports_credentials=True) call working and registers
/analitik without touching the large app.py file.
"""

import os


def CORS(app, *args, **kwargs):
    supports_credentials = bool(kwargs.get('supports_credentials'))

    try:
        from flask import send_from_directory, session

        def _serve_analitik():
            if os.environ.get('SECRET_KEY') and not session.get('user_email'):
                if os.path.exists('login.html'):
                    return send_from_directory('.', 'login.html')
            if os.path.exists('analitik.html'):
                return send_from_directory('.', 'analitik.html')
            return send_from_directory('.', 'index.html')

        if 'madmext_analitik_page' not in app.view_functions:
            app.add_url_rule('/analitik', 'madmext_analitik_page', _serve_analitik)
    except Exception as e:
        print('Analitik route shim error:', e)

    try:
        from trendyol_fallback import install as _install_trendyol_fallback
        _install_trendyol_fallback(app)
    except Exception as e:
        print('Trendyol fallback shim error:', e)

    try:
        @app.after_request
        def _mx_cors_headers(response):
            origin = '*'
            try:
                from flask import request
                origin = request.headers.get('Origin') or '*'
            except Exception:
                pass
            response.headers.setdefault('Access-Control-Allow-Origin', origin)
            response.headers.setdefault('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            response.headers.setdefault('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
            if supports_credentials:
                response.headers.setdefault('Access-Control-Allow-Credentials', 'true')
            return response
    except Exception as e:
        print('CORS shim header error:', e)

    return app
