"""Runtime compatibility helpers for Madmext Ads."""

import builtins
import os


def _madmext_render_template(template_name, *args, **kwargs):
    from flask import send_from_directory

    if template_name == 'modules/ai-ajans.html':
        return send_from_directory('modules', 'ai-ajans.html')

    if '/' in template_name:
        folder, filename = template_name.rsplit('/', 1)
        return send_from_directory(folder, filename)

    return send_from_directory('.', template_name)


builtins.render_template = _madmext_render_template


try:
    import requests as _requests

    _mx_original_post = _requests.post

    class _MXResponse:
        def __init__(self, payload, status_code=200):
            import json as _json
            self._payload = payload
            self.status_code = status_code
            self.text = _json.dumps(payload, ensure_ascii=False)

        def json(self):
            return self._payload

    def _extract_openai_text(result):
        if isinstance(result, dict) and result.get('output_text'):
            return result.get('output_text')
        parts = []
        for item in (result.get('output', []) if isinstance(result, dict) else []):
            for content in item.get('content', []) if isinstance(item, dict) else []:
                if isinstance(content, dict) and content.get('text'):
                    parts.append(content.get('text'))
        return '\n'.join(parts).strip()

    def _mx_post(url, *args, **kwargs):
        payload = kwargs.get('json') or {}
        use_openai = isinstance(payload, dict) and payload.get('provider') == 'openai'
        if use_openai and isinstance(url, str) and 'api.anthropic.com/v1/messages' in url:
            key = os.environ.get('OPENAI_API_KEY', '')
            if not key:
                return _MXResponse({'error': {'message': 'OPENAI_API_KEY Railway Variables icinde tanimli degil.'}}, 500)

            messages = payload.get('messages') or []
            prompt = ''
            if messages and isinstance(messages[0], dict):
                prompt = messages[0].get('content', '')
            model = payload.get('openai_model') or 'gpt-4.1-mini'

            r = _mx_original_post(
                'https://api.openai.com/v1/responses',
                headers={
                    'Authorization': 'Bearer ' + key,
                    'Content-Type': 'application/json'
                },
                json={
                    'model': model,
                    'input': prompt,
                    'max_output_tokens': int(payload.get('max_tokens', 1600) or 1600)
                },
                timeout=kwargs.get('timeout', 90)
            )
            try:
                result = r.json()
            except Exception:
                return _MXResponse({'error': {'message': 'OpenAI API yaniti parse edilemedi: ' + r.text[:200]}}, 500)
            if r.status_code >= 400:
                return _MXResponse(result, r.status_code)
            text = _extract_openai_text(result)
            return _MXResponse({'content': [{'type': 'text', 'text': text}], 'provider': 'openai', 'raw': result}, 200)

        return _mx_original_post(url, *args, **kwargs)

    _requests.post = _mx_post
except Exception:
    pass


# Analitik SPA route ve index.html script enjeksiyonu
try:
    import flask as _flask
    from flask import Response as _Response

    _mx_original_send_from_directory = _flask.send_from_directory

    def _mx_send_from_directory(directory, path, *args, **kwargs):
        try:
            if str(path) == 'index.html':
                full_path = os.path.join(str(directory), str(path))
                if os.path.exists(full_path):
                    with open(full_path, 'r', encoding='utf-8') as f:
                        html = f.read()
                    tag = '<script src="/modules/analitik-route.js?v=20260618"></script>'
                    if 'analitik-route.js' not in html:
                        html = html.replace('</body>', tag + '</body>')
                    return _Response(html, mimetype='text/html')
        except Exception:
            pass
        return _mx_original_send_from_directory(directory, path, *args, **kwargs)

    _flask.send_from_directory = _mx_send_from_directory

    _mx_original_wsgi_app = _flask.Flask.wsgi_app

    def _mx_wsgi_app(self, environ, start_response):
        if environ.get('PATH_INFO') == '/analitik':
            environ['PATH_INFO'] = '/'
        return _mx_original_wsgi_app(self, environ, start_response)

    _flask.Flask.wsgi_app = _mx_wsgi_app
except Exception:
    pass
