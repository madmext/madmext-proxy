"""Telegram Phase 1: secure webhook, viewer invites and account linking."""

import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import requests
from flask import jsonify, request, session


_memory_invites = {}
_memory_links = {}


def _now():
    return datetime.now(timezone.utc)


def _as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _ensure_schema(conn):
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS mx_telegram_links (
          telegram_chat_id BIGINT PRIMARY KEY,
          telegram_username TEXT,
          linked_email TEXT NOT NULL REFERENCES mx_users(email) ON UPDATE CASCADE ON DELETE CASCADE,
          role_snapshot TEXT NOT NULL DEFAULT 'viewer',
          linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS mx_telegram_links_email_idx ON mx_telegram_links(lower(linked_email))')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS mx_telegram_invites (
          invite_token TEXT PRIMARY KEY,
          created_by TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'viewer' CHECK (role = 'viewer'),
          max_uses INTEGER NOT NULL DEFAULT 1 CHECK (max_uses > 0),
          used_count INTEGER NOT NULL DEFAULT 0 CHECK (used_count >= 0),
          expires_at TIMESTAMPTZ NOT NULL,
          is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS mx_telegram_invites_expiry_idx ON mx_telegram_invites(expires_at)')
    conn.commit()
    cur.close()


def install(app, get_db, get_users, hash_pw, verify_pw, save_users, ai_engine=None):
    webhook_secret = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '').strip()
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()

    conn = get_db()
    if conn:
        try:
            _ensure_schema(conn)
        finally:
            conn.close()

    def audit(action, **details):
        writer = app.extensions.get('mx_audit')
        if writer:
            details.setdefault('actor_type', 'telegram_bot')
            writer(action, **details)

    def send_message(chat_id, text):
        if not bot_token:
            return False
        response = requests.post(
            'https://api.telegram.org/bot%s/sendMessage' % bot_token,
            json={'chat_id': chat_id, 'text': text}, timeout=15,
        )
        response.raise_for_status()
        return True

    def respond(chat_id, text, status=200, **extra):
        chunks = ai_engine.split_message(text) if ai_engine and hasattr(ai_engine, 'split_message') else [text]
        try:
            for chunk in chunks:
                send_message(chat_id, chunk)
        except Exception as exc:
            audit('telegram.delivery_failed', resource_type='telegram_chat',
                  resource_id=str(chat_id), result='failure', error_message=str(exc)[:500])
        return jsonify({'ok': True, 'reply': text, 'chunks': chunks, **extra}), status

    def find_user(email):
        email = (email or '').strip().lower()
        conn = get_db()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute('''SELECT email,name,password_hash,role,
                    COALESCE(is_active,TRUE),COALESCE(is_allowed,TRUE)
                    FROM mx_users WHERE lower(email)=lower(%s)''', (email,))
                row = cur.fetchone()
                cur.close()
                if row:
                    return dict(zip(('email','name','password_hash','role','is_active','is_allowed'), row))
            finally:
                conn.close()
        return next((u for u in get_users() if (u.get('email') or '').lower() == email), None)

    def create_viewer(email, password, name):
        conn = get_db()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute('''INSERT INTO mx_users(email,name,password_hash,role,is_active,is_allowed)
                               VALUES(%s,%s,%s,'viewer',TRUE,TRUE)''',
                            (email, name, hash_pw(password)))
                conn.commit(); cur.close()
                return
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        users = list(get_users())
        users.append({'email': email, 'name': name, 'password_hash': hash_pw(password), 'role': 'viewer',
                      'is_active': True, 'is_allowed': True})
        save_users(users)

    def get_link(chat_id):
        conn = get_db()
        if not conn:
            link = _memory_links.get(str(chat_id))
            return link if link and link.get('is_active', True) else None
        try:
            _ensure_schema(conn)
            cur = conn.cursor()
            cur.execute('''SELECT telegram_chat_id,telegram_username,linked_email,role_snapshot,linked_at,is_active
                           FROM mx_telegram_links WHERE telegram_chat_id=%s AND is_active=TRUE''', (chat_id,))
            row = cur.fetchone()
            cur.close()
            if not row:
                return None
            return dict(zip(('telegram_chat_id','telegram_username','linked_email','role_snapshot','linked_at','is_active'), row))
        finally:
            conn.close()

    def get_invite(token, lock=False, conn=None):
        if conn is None:
            invite = _memory_invites.get(token)
            return dict(invite) if invite else None
        cur = conn.cursor()
        sql = '''SELECT invite_token,created_by,role,max_uses,used_count,expires_at,is_active
                 FROM mx_telegram_invites WHERE invite_token=%s'''
        if lock:
            sql += ' FOR UPDATE'
        cur.execute(sql, (token,))
        row = cur.fetchone()
        cur.close()
        return dict(zip(('invite_token','created_by','role','max_uses','used_count','expires_at','is_active'), row)) if row else None

    def invite_error(invite):
        if not invite or not invite.get('is_active'):
            return 'Davet kodu geçersiz veya kapatılmış.'
        if _as_utc(invite.get('expires_at')) <= _now():
            return 'Davet kodunun süresi dolmuş.'
        if int(invite.get('used_count') or 0) >= int(invite.get('max_uses') or 1):
            return 'Davet kodunun kullanım hakkı dolmuş.'
        return None

    def save_link(chat_id, username, email, role, invite_token):
        conn = get_db()
        if not conn:
            invite = _memory_invites.get(invite_token)
            error = invite_error(invite)
            if error:
                return error
            invite['used_count'] = int(invite.get('used_count') or 0) + 1
            _memory_links[str(chat_id)] = {
                'telegram_chat_id': chat_id, 'telegram_username': username,
                'linked_email': email, 'role_snapshot': role, 'linked_at': _now(), 'is_active': True,
            }
            return None
        try:
            _ensure_schema(conn)
            invite = get_invite(invite_token, lock=True, conn=conn)
            error = invite_error(invite)
            if error:
                conn.rollback()
                return error
            cur = conn.cursor()
            cur.execute('''INSERT INTO mx_telegram_links
                (telegram_chat_id,telegram_username,linked_email,role_snapshot,linked_at,is_active)
                VALUES(%s,%s,%s,%s,NOW(),TRUE)
                ON CONFLICT(telegram_chat_id) DO UPDATE SET telegram_username=EXCLUDED.telegram_username,
                linked_email=EXCLUDED.linked_email,role_snapshot=EXCLUDED.role_snapshot,linked_at=NOW(),is_active=TRUE''',
                (chat_id, username, email, role))
            cur.execute('UPDATE mx_telegram_invites SET used_count=used_count+1 WHERE invite_token=%s', (invite_token,))
            conn.commit()
            cur.close()
            return None
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.post('/admin/telegram/invites')
    def create_telegram_invite():
        payload = request.get_json(silent=True) or {}
        if payload.get('role', 'viewer') != 'viewer':
            return jsonify({'error': 'Telegram davetleri yalnızca viewer rolü verebilir; daha yüksek roller admin panelinden atanır.'}), 400
        try:
            max_uses = min(max(int(payload.get('max_uses', 1)), 1), 100)
            hours = min(max(int(payload.get('expires_in_hours', 24)), 1), 24 * 30)
        except (TypeError, ValueError):
            return jsonify({'error': 'max_uses ve expires_in_hours tam sayı olmalı'}), 400
        token = secrets.token_urlsafe(32)
        expires_at = _now() + timedelta(hours=hours)
        created_by = session.get('user_email') or ''
        conn = get_db()
        if conn:
            try:
                _ensure_schema(conn)
                cur = conn.cursor()
                cur.execute('''INSERT INTO mx_telegram_invites
                    (invite_token,created_by,role,max_uses,used_count,expires_at,is_active)
                    VALUES(%s,%s,'viewer',%s,0,%s,TRUE)''', (token, created_by, max_uses, expires_at))
                conn.commit(); cur.close()
            finally:
                conn.close()
        else:
            _memory_invites[token] = {'invite_token': token, 'created_by': created_by, 'role': 'viewer',
                                      'max_uses': max_uses, 'used_count': 0, 'expires_at': expires_at, 'is_active': True}
        audit('telegram.invite_created', resource_type='telegram_invite', resource_id=token[:8],
              actor_type='user', actor_email=created_by, actor_role=session.get('user_role'),
              metadata={'role': 'viewer', 'max_uses': max_uses, 'expires_at': expires_at.isoformat()})
        return jsonify({'invite': {'token': token, 'role': 'viewer', 'max_uses': max_uses,
                                   'expires_at': expires_at.isoformat(),
                                   'deep_link': 'https://t.me/%s?start=%s' % (os.environ.get('TELEGRAM_BOT_USERNAME', '<bot_username>'), token)}}), 201

    @app.post('/telegram/webhook')
    def telegram_webhook():
        supplied = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if not webhook_secret or not hmac.compare_digest(supplied, webhook_secret):
            audit('telegram.webhook_rejected', result='failure', status_code=403,
                  error_message='invalid webhook secret')
            return jsonify({'error': 'Geçersiz Telegram webhook secret'}), 403

        update = request.get_json(silent=True) or {}
        message = update.get('message') or update.get('edited_message') or {}
        chat = message.get('chat') or {}
        chat_id = chat.get('id')
        username = chat.get('username') or (message.get('from') or {}).get('username') or ''
        text = str(message.get('text') or '').strip()
        if chat_id is None or not text:
            return jsonify({'ok': True, 'ignored': True}), 200

        link = get_link(chat_id)
        actor_email = link.get('linked_email') if link else None
        audit('telegram.message_received', resource_type='telegram_chat', resource_id=str(chat_id),
              actor_email=actor_email, actor_role=(link or {}).get('role_snapshot'),
              metadata={'command': text.split(' ', 1)[0][:40], 'update_id': update.get('update_id')})

        parts = text.split()
        command = parts[0].lower() if parts else ''
        if command == '/start':
            token = parts[1] if len(parts) > 1 else ''
            invite = get_invite(token)
            error = invite_error(invite)
            if error:
                return respond(chat_id, error, linked=False)
            return respond(chat_id,
                'Hesabını bağlamak için: /login DAVET_KODU email şifre\n'
                'Yeni viewer hesabı için: /register DAVET_KODU email şifre ad', linked=False)

        if command == '/login' and len(parts) >= 4:
            token, email, password = parts[1], parts[2].lower(), parts[3]
            invite = get_invite(token)
            error = invite_error(invite)
            user = find_user(email)
            if error:
                return respond(chat_id, error, linked=False)
            if not user or not verify_pw(user.get('password_hash'), password):
                audit('telegram.link_failed', actor_email=email, result='failure', status_code=401)
                return respond(chat_id, 'E-posta veya şifre hatalı.', linked=False)
            if user.get('is_active', True) is False or user.get('is_allowed', True) is False:
                return respond(chat_id, 'Bu hesap aktif değil veya giriş izni kapalı.', linked=False)
            role = user.get('role') or 'viewer'
            error = save_link(chat_id, username, email, role, token)
            if error:
                return respond(chat_id, error, linked=False)
            audit('telegram.account_linked', actor_email=email, actor_role=role,
                  resource_type='telegram_chat', resource_id=str(chat_id), result='success')
            return respond(chat_id, 'Hesap güvenli şekilde bağlandı.', linked=True, role=role)

        if command == '/register' and len(parts) >= 4:
            token, email, password = parts[1], parts[2].lower(), parts[3]
            name = ' '.join(parts[4:]).strip() or email.split('@', 1)[0]
            invite = get_invite(token)
            error = invite_error(invite)
            if error:
                return respond(chat_id, error, linked=False)
            if '@' not in email or len(password) < 8:
                return respond(chat_id, 'Geçerli e-posta ve en az 8 karakterli şifre gerekli.', linked=False)
            if find_user(email):
                return respond(chat_id, 'Bu e-posta zaten kayıtlı; /login kullanın.', linked=False)
            create_viewer(email, password, name)
            error = save_link(chat_id, username, email, 'viewer', token)
            if error:
                return respond(chat_id, error, linked=False)
            audit('telegram.viewer_registered', actor_email=email, actor_role='viewer',
                  resource_type='telegram_chat', resource_id=str(chat_id))
            return respond(chat_id, 'Viewer hesabı oluşturuldu ve Telegram bağlandı.', linked=True, role='viewer')

        if not link:
            return respond(chat_id, 'Önce admin tarafından oluşturulan davet linkiyle hesabını bağlamalısın.', linked=False)

        if not ai_engine:
            return respond(chat_id, 'Analiz motoru kullanılamıyor.', linked=True, role=link.get('role_snapshot'))
        if not ai_engine.check_rate_limit(chat_id):
            audit('telegram.rate_limited', actor_email=actor_email, actor_role=link.get('role_snapshot'),
                  resource_type='telegram_chat', resource_id=str(chat_id), result='blocked', status_code=429)
            return respond(chat_id, 'Dakikada en fazla 6 mesaj gönderebilirsiniz. Lütfen biraz bekleyin.',
                           status=429, linked=True, rate_limited=True)
        # Para ve yetki mutasyonları Faz 4'e kadar Claude'a dahi gönderilmez.
        if any(word in text.lower() for word in ('admin yap', 'rol değiştir', 'bütçe', 'budget')):
            audit('telegram.forbidden_request', actor_email=actor_email,
                  actor_role=link.get('role_snapshot'), reason='Phase 4 required', result='blocked')
            return respond(chat_id, 'Bu işlem Telegram üzerinden yapılamaz; yalnızca admin panelinden yönetilebilir.',
                           linked=True, role=link.get('role_snapshot'))
        result = ai_engine.answer(text, chat_id, actor_email, link.get('role_snapshot') or 'viewer')
        audit('telegram.analysis_completed', actor_email=actor_email, actor_role=link.get('role_snapshot'),
              resource_type='telegram_chat', resource_id=str(chat_id), result='success',
              metadata={'tokens_in': (result.get('usage') or {}).get('input_tokens', 0),
                        'tokens_out': (result.get('usage') or {}).get('output_tokens', 0)})
        return respond(chat_id, result.get('text') or 'Analiz sonucu üretilemedi.',
                       linked=True, role=link.get('role_snapshot'))

    app.extensions['mx_telegram'] = {'get_link': get_link, 'get_invite': get_invite}
