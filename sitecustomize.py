"""Runtime compatibility helpers for Madmext Ads."""

import builtins
import os


def _madmext_render_template(template_name, *args, **kwargs):
    from flask import send_from_directory
    if '/' in template_name:
        folder, filename = template_name.rsplit('/', 1)
        return send_from_directory(folder, filename)
    return send_from_directory('.', template_name)


builtins.render_template = _madmext_render_template


try:
    import flask as _flask
    from flask import Response as _Response

    _mx_original_wsgi_app = _flask.Flask.wsgi_app

    def _mx_file_html(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()

    def _mx_index_html():
        html = _mx_file_html('index.html')
        tag = '<script src="/modules/analitik-route.js?v=20260618-5"></script>'
        if 'analitik-route.js' not in html:
            html = html.replace('</body>', tag + '</body>')
        return html

    def _mx_wsgi_app(self, environ, start_response):
        path = environ.get('PATH_INFO') or '/'
        if path == '/analitik' and os.path.exists('analitik.html'):
            return _Response(_mx_file_html('analitik.html'), mimetype='text/html')(environ, start_response)
        if path == '/':
            return _Response(_mx_index_html(), mimetype='text/html')(environ, start_response)
        return _mx_original_wsgi_app(self, environ, start_response)

    _flask.Flask.wsgi_app = _mx_wsgi_app
except Exception:
    pass
