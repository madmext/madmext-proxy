"""Central security, authorization and audit layer for Madmext Ads."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone

from flask import g, jsonify, request, session


PUBLIC_PATHS = {'/', '/login', '/auth/login', '/auth/forgot-password', '/reset-password', '/runtime/health', '/theme.css'}
PUBLIC_PREFIXES = ('/static/',)
PROTECTED_PREFIXES = ('/api', '/ga4', '/gads', '/logs', '/claude', '/psi', '/trendyol', '/marketplace', '/onesignal', '/admin', '/proxy-xml', '/telegram')
MUTATING = {'POST', 'PUT', 'PATCH', 'DELETE'}
ROLE_PERMISSIONS = {
    'super_admin': {'*'},
    'admin': {'*'},
    'editor': {'data.read', 'report.export', 'ads.write', 'decision.review'},
    'viewer': {'data.read'},
}


def _has_permission(role, permission):
    allowed = ROLE_PERMISSIONS.get(role or 'viewer', set())
    return '*' in allowed or permission in allowed


def _is_admin_session():
    primary = os.environ.get('ADMIN_EMAIL', '').strip().lower()
    return session.get('user_role') in ('admin', 'super_admin') or (primary and session.get('user_email', '').lower() == primary)


def _required_permission(path):
    if path.startswith(('/admin', '/logs')):
        return 'admin'
    if path.startswith(('/gads/debug', '/gads/status', '/claude/test')):
        return 'admin'
    if request.method in ('GET', 'HEAD', 'OPTIONS') or path in ('/ga4', '/claude'):
        return 'data.read'
    if path == '/api':
        payload = request.get_json(silent=True) or {}
        return 'data.read' if str(payload.get('method', 'GET')).upper() == 'GET' else 'ads.write'
    if path.startswith(('/gads/budget', '/gads/toggle')):
        return 'ads.write'
    if path.startswith(('/trendyol/upload', '/onesignal/sync')):
        return 'ads.write'
    if path.startswith('/marketplace') and request.method in ('POST','PUT','PATCH','DELETE'):
        return 'marketplace.write'
    return 'data.read'


def _now():
    return datetime.now(timezone.utc).isoformat()


def _client_ip():
    forwarded = request.headers.get('X-Forwarded-For', '')
    return (forwarded.split(',', 1)[0].strip() if forwarded else request.remote_addr) or ''


def _safe_details():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {}
    blocked = {'password', 'token', 'access_token', 'refresh_token', 'secret', 'otp', 'code', 'api_key'}
    return {k: ('[REDACTED]' if k.lower() in blocked else v) for k, v in data.items() if k.lower() not in {'messages', 'body'}}


def _init_audit_db(get_db):
    conn = get_db()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mx_audit_logs (
              id BIGSERIAL PRIMARY KEY, event_id TEXT UNIQUE NOT NULL,
              occurred_at TIMESTAMPTZ NOT NULL, actor_email TEXT, actor_name TEXT,
              actor_role TEXT, actor_type TEXT NOT NULL, action TEXT NOT NULL,
              resource_type TEXT, resource_id TEXT, method TEXT, path TEXT,
              old_value JSONB, new_value JSONB, reason TEXT, result TEXT NOT NULL,
              status_code INTEGER, error_message TEXT, ip_address TEXT,
              user_agent TEXT, request_id TEXT, metadata JSONB
            )
        """)
        cur.execute('CREATE INDEX IF NOT EXISTS mx_audit_time_idx ON mx_audit_logs (occurred_at DESC)')
        cur.execute('CREATE INDEX IF NOT EXISTS mx_audit_actor_idx ON mx_audit_logs (actor_email, occurred_at DESC)')
        cur.execute('CREATE INDEX IF NOT EXISTS mx_audit_action_idx ON mx_audit_logs (action, occurred_at DESC)')
        conn.commit()
        cur.close()
    finally:
        conn.close()


def _write_audit(get_db, event):
    conn = get_db()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
          INSERT INTO mx_audit_logs(
            event_id,occurred_at,actor_email,actor_name,actor_role,actor_type,
            action,resource_type,resource_id,method,path,old_value,new_value,
            reason,result,status_code,error_message,ip_address,user_agent,request_id,metadata
          ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        """, (
          event['event_id'], event['occurred_at'], event.get('actor_email'), event.get('actor_name'),
          event.get('actor_role'), event.get('actor_type', 'user'), event['action'],
          event.get('resource_type'), event.get('resource_id'), event.get('method'), event.get('path'),
          json.dumps(event.get('old_value')), json.dumps(event.get('new_value')), event.get('reason'),
          event.get('result', 'success'), event.get('status_code'), event.get('error_message'),
          event.get('ip_address'), event.get('user_agent'), event.get('request_id'),
          json.dumps(event.get('metadata') or {})
        ))
        conn.commit()
        cur.close()
        return True
    except Exception as exc:
        print('audit write:', exc)
        return False
    finally:
        conn.close()


def _totp(secret, timestamp=None):
    raw = secret.strip().replace(' ', '').upper()
    raw += '=' * ((8 - len(raw) % 8) % 8)
    key = base64.b32decode(raw)
    counter = int((timestamp or time.time()) // 30).to_bytes(8, 'big')
    digest = hmac.new(key, counter, hashlib.sha1).digest()
    offset = digest[-1] & 15
    value = (int.from_bytes(digest[offset:offset + 4], 'big') & 0x7fffffff) % 1000000
    return f'{value:06d}'


def _verify_totp(secret, code):
    return any(secrets.compare_digest(_totp(secret, time.time() + step * 30), str(code or '').zfill(6)) for step in (-1, 0, 1))


def install(app, get_db):
    _init_audit_db(get_db)
    otp_secret = os.environ.get('ADMIN_OTP_SECRET', '').strip()
    otp_ttl = int(os.environ.get('ADMIN_OTP_TTL_SECONDS', '600'))

    def audit(action, **extra):
        event = {
            'event_id': str(uuid.uuid4()), 'occurred_at': _now(),
            'actor_email': session.get('user_email'), 'actor_name': session.get('user_name'),
            'actor_role': session.get('user_role'), 'actor_type': extra.pop('actor_type', 'user'),
            'action': action, 'method': request.method, 'path': request.path,
            'ip_address': _client_ip(), 'user_agent': request.headers.get('User-Agent', '')[:500],
            'request_id': getattr(g, 'request_id', None), **extra,
        }
        return _write_audit(get_db, event)

    app.extensions['mx_audit'] = audit

    @app.before_request
    def mx_security_gate():
        g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        path = request.path.rstrip('/') or '/'
        # Telegram cannot carry a browser session. The webhook performs its own
        # constant-time secret-token verification inside telegram_flow.py.
        if path == '/telegram/webhook':
            return None
        is_public = path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES)
        if path.startswith('/modules/') or path.endswith(('.css', '.js', '.png', '.svg', '.ico')):
            is_public = True
        if not is_public and (path.startswith(PROTECTED_PREFIXES) or path not in PUBLIC_PATHS):
            if not session.get('user_email'):
                if path.startswith(PROTECTED_PREFIXES):
                    return jsonify({'error': 'Oturum gerekli', 'request_id': g.request_id}), 401
                return None

        if path.startswith('/admin') and not _is_admin_session():
            return jsonify({'error': 'Admin yetkisi gerekli', 'request_id': g.request_id}), 403

        if path.startswith(PROTECTED_PREFIXES):
            required = _required_permission(path)
            role = session.get('user_role') or 'viewer'
            if required == 'admin' and not _is_admin_session():
                return jsonify({'error': 'Admin yetkisi gerekli', 'request_id': g.request_id}), 403
            checker = app.extensions.get('mx_has_permission')
            allowed = checker(role, required) if checker else _has_permission(role, required)
            if required != 'admin' and not allowed:
                return jsonify({'error': 'Bu işlem için yetkiniz yok', 'permission': required, 'request_id': g.request_id}), 403

    @app.after_request
    def mx_security_headers_and_audit(response):
        response.headers['X-Request-ID'] = getattr(g, 'request_id', '')
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        # telegram_flow writes a purpose-built audit event without message text.
        # Skipping the generic body audit prevents credentials sent during the
        # Phase 1 link flow from ever reaching mx_audit_logs.
        if request.method in MUTATING and request.path != '/telegram/webhook':
            action = 'auth.login' if request.path == '/auth/login' else 'http.' + request.method.lower()
            audit(action, resource_type='endpoint', resource_id=request.path,
                  new_value=_safe_details(), result='success' if response.status_code < 400 else 'failure',
                  status_code=response.status_code)
        return response

    @app.post('/auth/admin-otp/verify')
    def admin_otp_verify():
        if not _is_admin_session():
            return jsonify({'error': 'Admin yetkisi gerekli'}), 403
        if not otp_secret:
            return jsonify({'error': 'ADMIN_OTP_SECRET yapılandırılmamış'}), 503
        code = (request.get_json(silent=True) or {}).get('code')
        if not _verify_totp(otp_secret, code):
            audit('auth.otp_failed', result='failure', status_code=401)
            return jsonify({'error': 'OTP kodu geçersiz'}), 401
        session['admin_otp_verified_at'] = int(time.time())
        audit('auth.otp_verified', result='success', status_code=200)
        return jsonify({'ok': True, 'expires_in': otp_ttl})

    @app.get('/auth/admin-otp/status')
    def admin_otp_status():
        if not _is_admin_session():
            return jsonify({'error': 'Admin yetkisi gerekli'}), 403
        verified = int(time.time()) - int(session.get('admin_otp_verified_at') or 0) < otp_ttl
        return jsonify({'configured': bool(otp_secret), 'verified': verified, 'expires_in': max(0, otp_ttl - (int(time.time()) - int(session.get('admin_otp_verified_at') or 0)))})

    @app.get('/admin/audit-logs')
    def admin_audit_logs():
        if otp_secret and int(time.time()) - int(session.get('admin_otp_verified_at') or 0) >= otp_ttl:
            return jsonify({'error': 'OTP doğrulaması gerekli', 'otp_required': True}), 403
        conn = get_db()
        if not conn:
            return jsonify({'error': 'Veritabanı bağlantısı yok'}), 503
        try:
            limit = min(max(int(request.args.get('limit', 100)), 1), 500)
            cur = conn.cursor()
            cur.execute("""SELECT event_id,occurred_at,actor_email,actor_name,actor_role,actor_type,
              action,resource_type,resource_id,method,path,old_value,new_value,reason,result,
              status_code,error_message,ip_address,request_id,metadata
              FROM mx_audit_logs ORDER BY occurred_at DESC LIMIT %s""", (limit,))
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            for row in rows:
                row['occurred_at'] = row['occurred_at'].isoformat()
            cur.close()
            return jsonify({'items': rows, 'count': len(rows)})
        finally:
            conn.close()

    return audit
