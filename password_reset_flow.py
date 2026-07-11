import os
import json
import secrets
import hashlib
import smtplib
import socket
import base64
import requests
from email.mime.text import MIMEText
from datetime import datetime, timedelta


def _now():
    return datetime.utcnow()


def _iso(dt):
    return dt.isoformat() if hasattr(dt, 'isoformat') else (dt or '')


def _token_hash(token):
    return hashlib.sha256((token or '').encode()).hexdigest()


def _base_url():
    return (os.environ.get('APP_BASE_URL') or os.environ.get('PUBLIC_BASE_URL') or 'https://web-production-e5865.up.railway.app').rstrip('/')


def _mail_configured():
    mode = (os.environ.get('MAIL_MODE') or '').strip().lower()
    if mode == 'gmail_api':
        return bool(os.environ.get('GMAIL_CLIENT_ID') and os.environ.get('GMAIL_CLIENT_SECRET') and os.environ.get('GMAIL_REFRESH_TOKEN'))
    return bool((os.environ.get('SMTP_HOST') or os.environ.get('OTP_SMTP_HOST')) and (os.environ.get('SMTP_USER') or os.environ.get('OTP_SMTP_USER')) and (os.environ.get('SMTP_PASSWORD') or os.environ.get('OTP_SMTP_PASSWORD')))


def _resolve_ipv4(host):
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
        for info in infos:
            ip = info[4][0]
            if ip:
                return ip
    except Exception:
        pass
    return host


class _IPv4SMTP(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        ip = _resolve_ipv4(host)
        return socket.create_connection((ip, port), timeout, self.source_address)


class _IPv4SMTP_SSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        ip = _resolve_ipv4(host)
        new_socket = socket.create_connection((ip, port), timeout, self.source_address)
        return self.context.wrap_socket(new_socket, server_hostname=host)


def _send_gmail_api(to_email, subject, body):
    client_id = os.environ.get('GMAIL_CLIENT_ID')
    client_secret = os.environ.get('GMAIL_CLIENT_SECRET')
    refresh_token = os.environ.get('GMAIL_REFRESH_TOKEN')
    sender = os.environ.get('GMAIL_SENDER') or os.environ.get('SMTP_FROM_EMAIL') or os.environ.get('SMTP_USER')
    if not (client_id and client_secret and refresh_token and sender):
        return {'sent': False, 'error': 'Gmail API değişkenleri eksik'}
    try:
        token_res = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            },
            timeout=25
        )
        if token_res.status_code >= 400:
            return {'sent': False, 'error': 'Gmail token hatası: ' + token_res.text[:500]}
        access_token = token_res.json().get('access_token')
        if not access_token:
            return {'sent': False, 'error': 'Gmail access_token alınamadı'}

        msg = MIMEText(body, 'plain', 'utf-8')
        msg['To'] = to_email
        msg['From'] = sender
        msg['Subject'] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        send_res = requests.post(
            'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
            headers={'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'},
            json={'raw': raw},
            timeout=25
        )
        if send_res.status_code >= 400:
            return {'sent': False, 'error': 'Gmail gönderim hatası: ' + send_res.text[:500]}
        return {'sent': True}
    except Exception as e:
        return {'sent': False, 'error': 'Gmail API exception: ' + str(e)}


def _send_smtp(to_email, subject, body):
    host = os.environ.get('SMTP_HOST') or os.environ.get('OTP_SMTP_HOST')
    port = int(os.environ.get('SMTP_PORT') or os.environ.get('OTP_SMTP_PORT') or 587)
    user = os.environ.get('SMTP_USER') or os.environ.get('OTP_SMTP_USER')
    password = os.environ.get('SMTP_PASSWORD') or os.environ.get('OTP_SMTP_PASSWORD')
    from_email = os.environ.get('SMTP_FROM_EMAIL') or os.environ.get('OTP_FROM_EMAIL') or user
    smtp_ssl = str(os.environ.get('SMTP_SSL') or os.environ.get('OTP_SMTP_SSL') or '').strip().lower() in ('1', 'true', 'yes', 'on')
    force_ipv4 = str(os.environ.get('SMTP_FORCE_IPV4') or 'true').strip().lower() not in ('0', 'false', 'no', 'off')
    use_ssl = smtp_ssl or port == 465
    if not (host and user and password and from_email):
        return {'sent': False, 'error': 'SMTP değişkenleri eksik'}
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    smtp_cls = _IPv4SMTP if force_ipv4 else smtplib.SMTP
    smtp_ssl_cls = _IPv4SMTP_SSL if force_ipv4 else smtplib.SMTP_SSL
    try:
        if use_ssl:
            with smtp_ssl_cls(host, port, timeout=25) as s:
                s.login(user, password)
                s.sendmail(from_email, [to_email], msg.as_string())
        else:
            with smtp_cls(host, port, timeout=25) as s:
                s.ehlo(); s.starttls(); s.ehlo()
                s.login(user, password)
                s.sendmail(from_email, [to_email], msg.as_string())
        return {'sent': True}
    except Exception as e:
        return {'sent': False, 'error': str(e)}


def _send_mail(to_email, subject, body):
    mode = (os.environ.get('MAIL_MODE') or '').strip().lower()
    if mode == 'gmail_api':
        res = _send_gmail_api(to_email, subject, body)
        if res.get('sent'):
            return res
        if str(os.environ.get('MAIL_FALLBACK_SMTP') or '').strip().lower() in ('1', 'true', 'yes', 'on'):
            smtp_res = _send_smtp(to_email, subject, body)
            if smtp_res.get('sent'):
                return smtp_res
            return {'sent': False, 'error': res.get('error') + ' | SMTP fallback: ' + smtp_res.get('error', '')}
        return res
    return _send_smtp(to_email, subject, body)


def install(app, get_db, hash_pw, read_logs=None, write_logs=None):
    from flask import request, jsonify, session, send_from_directory

    def require_admin():
        primary = os.environ.get('ADMIN_EMAIL', '').strip().lower()
        if session.get('user_role') not in ('admin', 'super_admin') and session.get('user_email','').lower() != primary:
            return jsonify({'error': 'Admin gerekli'}), 403
        return None

    def init_table():
        conn = get_db()
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS mx_password_resets (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL,
                message TEXT,
                token_hash TEXT,
                status TEXT DEFAULT 'pending',
                request_time TIMESTAMP DEFAULT NOW(),
                approved_by TEXT,
                approved_at TIMESTAMP,
                declined_by TEXT,
                declined_at TIMESTAMP,
                used_at TIMESTAMP,
                expires_at TIMESTAMP,
                mail_sent BOOLEAN DEFAULT FALSE,
                mail_error TEXT
            )''')
            conn.commit(); cur.close(); conn.close()
            return True
        except Exception as e:
            print('password reset init:', e)
            try: conn.close()
            except Exception: pass
            return False

    init_table()

    def log_fallback_get():
        if not read_logs:
            return []
        data = read_logs()
        return data.get('passwordResetRequests') or data.get('resetRequests') or []

    def log_fallback_save(reqs):
        if not (read_logs and write_logs):
            return
        data = read_logs()
        data['passwordResetRequests'] = reqs
        write_logs(data)

    def create_request(email, message):
        conn = get_db()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute('INSERT INTO mx_password_resets(email,message,status) VALUES(%s,%s,%s) RETURNING id', (email, message, 'pending'))
                rid = cur.fetchone()[0]
                conn.commit(); cur.close(); conn.close()
                return {'id': rid, 'email': email, 'status': 'pending'}
            except Exception as e:
                try: conn.close()
                except Exception: pass
                return {'error': str(e)}
        reqs = log_fallback_get()
        rid = int(max([r.get('id', 0) for r in reqs] or [0])) + 1
        reqs.insert(0, {'id': rid, 'email': email, 'message': message, 'status': 'pending', 'request_time': _now().isoformat()})
        log_fallback_save(reqs)
        return {'id': rid, 'email': email, 'status': 'pending'}

    def list_requests():
        conn = get_db()
        if conn:
            try:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute('SELECT id,email,message,status,request_time,approved_by,approved_at,declined_by,declined_at,used_at,expires_at,mail_sent,mail_error FROM mx_password_resets ORDER BY request_time DESC LIMIT 200')
                rows = []
                for r in cur.fetchall():
                    d = dict(r)
                    for k, v in list(d.items()):
                        if hasattr(v, 'isoformat'):
                            d[k] = v.isoformat()
                    rows.append(d)
                cur.close(); conn.close()
                return rows
            except Exception as e:
                try: conn.close()
                except Exception: pass
                return [{'error': str(e)}]
        return log_fallback_get()

    def find_request(req_id):
        conn = get_db()
        if conn:
            try:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute('SELECT * FROM mx_password_resets WHERE id=%s', (req_id,))
                row = cur.fetchone()
                cur.close(); conn.close()
                return dict(row) if row else None
            except Exception:
                try: conn.close()
                except Exception: pass
                return None
        for r in log_fallback_get():
            if int(r.get('id', -1)) == int(req_id):
                return r
        return None

    def approve_request(req_id):
        req = find_request(req_id)
        if not req:
            return {'error': 'Talep bulunamadı'}
        if req.get('status') not in ('pending', 'approved'):
            return {'error': 'Bu talep artık onaylanamaz'}
        token = secrets.token_urlsafe(32)
        th = _token_hash(token)
        expires = _now() + timedelta(hours=24)
        reset_url = _base_url() + '/reset-password?token=' + token
        mail_body = (
            'Madmext Ads şifre değiştirme talebiniz onaylandı.\n\n'
            'Şifrenizi değiştirmek için aşağıdaki bağlantıyı açın:\n'
            + reset_url + '\n\n'
            'Bu bağlantı 24 saat geçerlidir. Talep size ait değilse bu e-postayı dikkate almayın.'
        )
        mail = _send_mail(req.get('email'), 'Madmext Ads şifre değiştirme bağlantısı', mail_body)
        conn = get_db()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute('''UPDATE mx_password_resets SET token_hash=%s,status=%s,approved_by=%s,approved_at=NOW(),expires_at=%s,mail_sent=%s,mail_error=%s WHERE id=%s''',
                            (th, 'approved', session.get('user_email',''), expires, bool(mail.get('sent')), mail.get('error'), req_id))
                conn.commit(); cur.close(); conn.close()
            except Exception as e:
                try: conn.close()
                except Exception: pass
                return {'error': str(e)}
        else:
            reqs = log_fallback_get()
            for r in reqs:
                if int(r.get('id', -1)) == int(req_id):
                    r.update({'token_hash': th, 'status':'approved', 'approved_by': session.get('user_email',''), 'approved_at': _now().isoformat(), 'expires_at': expires.isoformat(), 'mail_sent': bool(mail.get('sent')), 'mail_error': mail.get('error')})
            log_fallback_save(reqs)
        return {'ok': True, 'mail_sent': bool(mail.get('sent')), 'mail_error': mail.get('error'), 'reset_url': reset_url if not mail.get('sent') else None}

    def decline_request(req_id):
        conn = get_db()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute('UPDATE mx_password_resets SET status=%s,declined_by=%s,declined_at=NOW() WHERE id=%s AND status=%s', ('declined', session.get('user_email',''), req_id, 'pending'))
                conn.commit(); cur.close(); conn.close()
                return {'ok': True}
            except Exception as e:
                try: conn.close()
                except Exception: pass
                return {'error': str(e)}
        reqs = log_fallback_get()
        for r in reqs:
            if int(r.get('id', -1)) == int(req_id):
                r.update({'status':'declined','declined_by':session.get('user_email',''),'declined_at':_now().isoformat()})
        log_fallback_save(reqs)
        return {'ok': True}

    def token_request(token):
        th = _token_hash(token)
        conn = get_db()
        if conn:
            try:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute('SELECT * FROM mx_password_resets WHERE token_hash=%s AND status=%s', (th, 'approved'))
                row = cur.fetchone()
                cur.close(); conn.close()
                return dict(row) if row else None
            except Exception:
                try: conn.close()
                except Exception: pass
                return None
        for r in log_fallback_get():
            if r.get('token_hash') == th and r.get('status') == 'approved':
                return r
        return None

    def use_token(token, new_password):
        if not new_password or len(new_password) < 6:
            return {'error': 'Şifre en az 6 karakter olmalı'}
        req = token_request(token)
        if not req:
            return {'error': 'Geçersiz veya kullanılmış bağlantı'}
        exp = req.get('expires_at')
        if exp:
            try:
                exp_dt = exp if isinstance(exp, datetime) else datetime.fromisoformat(str(exp).replace('Z',''))
                if _now() > exp_dt:
                    return {'error': 'Bağlantının süresi dolmuş'}
            except Exception:
                pass
        email = req.get('email')
        conn = get_db()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute('UPDATE mx_users SET password_hash=%s WHERE lower(email)=lower(%s)', (hash_pw(new_password), email))
                cur.execute('UPDATE mx_password_resets SET status=%s,used_at=NOW() WHERE id=%s', ('used', req.get('id')))
                conn.commit(); cur.close(); conn.close()
                return {'ok': True}
            except Exception as e:
                try: conn.close()
                except Exception: pass
                return {'error': str(e)}
        return {'error': 'Database bağlantısı yok'}

    @app.before_request
    def _password_reset_before_request():
        path = request.path.rstrip('/') or '/'
        if path == '/auth/forgot-password' and request.method == 'POST':
            data = request.get_json(silent=True) or {}
            email = (data.get('email') or '').strip().lower()
            message = data.get('message') or 'Şifremi unuttum'
            if not email:
                return jsonify({'error': 'Email zorunlu'}), 400
            create_request(email, message)
            return jsonify({'ok': True, 'message': 'Talebiniz yönetici onayına gönderildi.'})
        if path == '/admin/reset-requests' and request.method == 'GET':
            r = require_admin()
            if r: return r
            return jsonify(list_requests())
        if path.startswith('/admin/reset-requests/') and request.method == 'POST':
            r = require_admin()
            if r: return r
            parts = path.split('/')
            try:
                req_id = int(parts[3])
            except Exception:
                return jsonify({'error': 'Geçersiz talep'}), 400
            action = parts[4] if len(parts) > 4 else ''
            if action == 'approve':
                res = approve_request(req_id)
            elif action == 'decline':
                res = decline_request(req_id)
            else:
                res = {'error': 'Bilinmeyen işlem'}
            return jsonify(res), (400 if res.get('error') else 200)
        if path == '/auth/reset-info' and request.method == 'GET':
            token = request.args.get('token','')
            req = token_request(token)
            if not req:
                return jsonify({'error': 'Geçersiz bağlantı'}), 400
            return jsonify({'ok': True, 'email': req.get('email'), 'expires_at': _iso(req.get('expires_at'))})
        if path == '/auth/reset-password' and request.method == 'POST':
            data = request.get_json(silent=True) or {}
            res = use_token(data.get('token',''), data.get('password',''))
            return jsonify(res), (400 if res.get('error') else 200)
        return None

    @app.route('/reset-password')
    def reset_password_page():
        return send_from_directory('.', 'reset-password.html')

    print('✓ password_reset_flow installed')
