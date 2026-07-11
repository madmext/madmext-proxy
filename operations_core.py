"""Operational safety gates for Madmext Ads."""
import os
from flask import jsonify, request


def _bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def install(app):
    def state():
        return {
            'shadow_mode': _bool('SHADOW_MODE', True),
            'provider_writes_enabled': _bool('PROVIDER_WRITES_ENABLED', False),
            'global_kill_switch': _bool('GLOBAL_KILL_SWITCH', True),
            'meta_writes_enabled': _bool('META_WRITES_ENABLED', False),
            'google_writes_enabled': _bool('GOOGLE_WRITES_ENABLED', False),
            'marketplace_writes_enabled': _bool('MARKETPLACE_WRITES_ENABLED', False),
        }

    def write_allowed(channel):
        s = state()
        if s['shadow_mode'] or s['global_kill_switch'] or not s['provider_writes_enabled']:
            return False
        return s.get(channel + '_writes_enabled', False)

    app.extensions['mx_operation_state'] = state
    app.extensions['mx_provider_write_allowed'] = write_allowed

    @app.before_request
    def provider_write_gate():
        path = request.path.rstrip('/')
        channel = None
        is_provider_write = False
        if path == '/api' and request.method == 'POST':
            payload = request.get_json(silent=True) or {}
            is_provider_write = str(payload.get('method', 'GET')).upper() != 'GET'
            channel = 'meta'
        elif path in ('/gads/budget', '/gads/toggle') and request.method == 'POST':
            is_provider_write = True
            channel = 'google'
        elif path.startswith('/marketplace/applications/') and request.method == 'POST':
            is_provider_write = True
            channel = 'marketplace'
        if is_provider_write and not write_allowed(channel):
            s = state()
            return jsonify({
                'error': 'Gerçek kanal işlemleri güvenli mod nedeniyle kapalı',
                'code': 'provider_writes_disabled',
                'channel': channel,
                'shadow_mode': s['shadow_mode'],
                'global_kill_switch': s['global_kill_switch'],
            }), 423

    @app.get('/runtime/operation-mode')
    def operation_mode():
        s = state()
        s['effective_mode'] = 'shadow' if s['shadow_mode'] else ('stopped' if s['global_kill_switch'] else 'controlled-write')
        return jsonify(s)
