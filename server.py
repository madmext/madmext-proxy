from flask import request, jsonify, session
from urllib.parse import unquote
from app import app, get_db, get_users, hash_pw, password_needs_rehash, verify_pw, read_logs, save_users, write_logs
import password_reset_flow


def _is_admin():
    from app import ADMIN_EMAIL
    return session.get('user_role') in ('admin', 'super_admin') or session.get('user_email','').lower() == ADMIN_EMAIL.lower()


def _admin_required():
    if not _is_admin():
        return jsonify({'error': 'Admin gerekli'}), 403
    return None


def _bool(v, default=False):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    return str(v).strip().lower() in ('1', 'true', 'yes', 'on', 'evet')


def _db_init_user_meta():
    conn = get_db()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS surname TEXT")
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS phone TEXT")
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS is_allowed BOOLEAN DEFAULT TRUE")
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS show_panel_help BOOLEAN DEFAULT FALSE")
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS new_panel BOOLEAN DEFAULT FALSE")
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS personnel BOOLEAN DEFAULT FALSE")
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()")
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP")
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0")
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS two_factor_reset_at TIMESTAMP")
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print('user meta init:', e)
        try:
            conn.close()
        except Exception:
            pass
        return False


def _db_users(private=False):
    conn = get_db()
    if not conn:
        return None
    _db_init_user_meta()
    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        select_pw = ", password_hash" if private else ""
        cur.execute(f"""
            SELECT
              row_number() OVER (ORDER BY created_at, email) AS user_no,
              email,
              name,
              surname,
              phone,
              role,
              created_at,
              updated_at,
              last_login,
              login_count,
              COALESCE(is_active, TRUE) AS is_active,
              COALESCE(is_allowed, TRUE) AS is_allowed,
              COALESCE(show_panel_help, FALSE) AS show_panel_help,
              COALESCE(new_panel, FALSE) AS new_panel,
              COALESCE(personnel, FALSE) AS personnel,
              two_factor_reset_at
              {select_pw}
            FROM mx_users
            ORDER BY created_at, email
        """)
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            for k, v in list(d.items()):
                if hasattr(v, 'isoformat'):
                    d[k] = v.isoformat()
            rows.append(d)
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print('db users extended:', e)
        try:
            conn.close()
        except Exception:
            pass
        return None


def _db_user_private(email):
    users = _db_users(private=True)
    if users is None:
        return None
    return next((u for u in users if (u.get('email') or '').lower() == email.lower()), None)


def _db_add_user(payload):
    conn = get_db()
    if not conn:
        return False
    _db_init_user_meta()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO mx_users(
                email,name,surname,phone,password_hash,role,is_active,is_allowed,
                show_panel_help,new_panel,personnel,updated_at
            )
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
        """, (
            payload['email'], payload.get('name'), payload.get('surname'), payload.get('phone'),
            payload['password_hash'], payload.get('role', 'viewer'),
            payload.get('is_active', True), payload.get('is_allowed', True),
            payload.get('show_panel_help', False), payload.get('new_panel', False),
            payload.get('personnel', False)
        ))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print('db_add_user:', e)
        try:
            conn.close()
        except Exception:
            pass
        return False


def _db_delete_user(email):
    conn = get_db()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM mx_users WHERE lower(email)=lower(%s)', (email,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print('db_delete_user:', e)
        try:
            conn.close()
        except Exception:
            pass
        return False


def _db_patch_user(email, **fields):
    conn = get_db()
    if not conn:
        return False
    _db_init_user_meta()
    allowed = {
        'name': 'name',
        'surname': 'surname',
        'phone': 'phone',
        'role': 'role',
        'password_hash': 'password_hash',
        'is_active': 'is_active',
        'is_allowed': 'is_allowed',
        'show_panel_help': 'show_panel_help',
        'new_panel': 'new_panel',
        'personnel': 'personnel'
    }
    sets = []
    vals = []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{allowed[k]}=%s")
            vals.append(v)
    if not sets:
        return True
    sets.append('updated_at=NOW()')
    vals.append(email)
    try:
        cur = conn.cursor()
        cur.execute('UPDATE mx_users SET ' + ','.join(sets) + ' WHERE lower(email)=lower(%s)', vals)
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print('db_patch_user:', e)
        try:
            conn.close()
        except Exception:
            pass
        return False


def _db_record_login(email):
    conn = get_db()
    if not conn:
        return False
    _db_init_user_meta()
    try:
        cur = conn.cursor()
        cur.execute('UPDATE mx_users SET last_login=NOW(), login_count=COALESCE(login_count,0)+1 WHERE lower(email)=lower(%s)', (email,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print('db_record_login:', e)
        try:
            conn.close()
        except Exception:
            pass
        return False


def _db_2fa_reset(email):
    conn = get_db()
    if not conn:
        return False
    _db_init_user_meta()
    try:
        cur = conn.cursor()
        cur.execute('UPDATE mx_users SET two_factor_reset_at=NOW(), updated_at=NOW() WHERE lower(email)=lower(%s)', (email,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print('db_2fa_reset:', e)
        try:
            conn.close()
        except Exception:
            pass
        return False


def _fallback_users():
    return get_users()


def _save_fallback_users(users):
    save_users(users)


def _fallback_public(users):
    out = []
    for i, u in enumerate(users, 1):
        out.append({
            'user_no': i,
            'email': u.get('email'),
            'name': u.get('name'),
            'surname': u.get('surname') or '',
            'phone': u.get('phone') or '',
            'role': u.get('role', 'viewer'),
            'created_at': u.get('created_at') or '',
            'updated_at': u.get('updated_at') or '',
            'last_login': u.get('last_login') or '',
            'login_count': u.get('login_count') or 0,
            'is_active': u.get('is_active', True),
            'is_allowed': u.get('is_allowed', True),
            'show_panel_help': u.get('show_panel_help', False),
            'new_panel': u.get('new_panel', False),
            'personnel': u.get('personnel', False),
            'two_factor_reset_at': u.get('two_factor_reset_at') or ''
        })
    return out


def _get_all_users_public():
    users = _db_users()
    if users is not None:
        return users
    return _fallback_public(_fallback_users())


@app.before_request
def _auth_and_admin_users_override():
    path = request.path.rstrip('/') or '/'

    if path == '/auth/login' and request.method == 'POST':
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        user = _db_user_private(email)
        user_from_db = user is not None
        if user is None:
            fallback = _fallback_users()
            user = next((u for u in fallback if (u.get('email') or '').lower() == email.lower()), None)
        if not user or not verify_pw(user.get('password_hash'), password):
            return jsonify({'error': 'Email veya şifre hatalı'}), 401
        if user.get('is_allowed', True) is False:
            return jsonify({'error': 'Kullanıcı için giriş izni kapalı'}), 403
        if user.get('is_active', True) is False:
            return jsonify({'error': 'Kullanıcı pasif durumda'}), 403
        if password_needs_rehash(user.get('password_hash')):
            upgraded_hash = hash_pw(password)
            if user_from_db:
                _db_patch_user(email, password_hash=upgraded_hash)
            else:
                fallback = _fallback_users()
                for fallback_user in fallback:
                    if (fallback_user.get('email') or '').lower() == email:
                        fallback_user['password_hash'] = upgraded_hash
                        break
                _save_fallback_users(fallback)
            user['password_hash'] = upgraded_hash
        session['user_email'] = user.get('email')
        session['user_name'] = ((user.get('name') or '') + ' ' + (user.get('surname') or '')).strip() or user.get('email')
        from app import ADMIN_EMAIL
        session['user_role'] = 'super_admin' if (user.get('email') or '').lower() == ADMIN_EMAIL.lower() else (user.get('role') or 'viewer')
        session.permanent = True
        _db_record_login(email)
        return jsonify({'ok': True, 'user': {'email': user.get('email'), 'name': session['user_name'], 'role': session['user_role']}})

    if not path.startswith('/admin/users'):
        return None

    r = _admin_required()
    if r:
        return r

    if path == '/admin/users' and request.method == 'GET':
        return jsonify(_get_all_users_public())

    if path == '/admin/users' and request.method == 'POST':
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip().lower()
        name = (data.get('name') or '').strip()
        surname = (data.get('surname') or '').strip()
        phone = (data.get('phone') or '').strip()
        password = data.get('password') or ''
        role = data.get('role') or 'viewer'
        if not email:
            return jsonify({'error': 'E-posta zorunlu'}), 400
        if not password or len(password) < 6:
            return jsonify({'error': 'Şifre en az 6 karakter olmalı'}), 400
        users = _get_all_users_public()
        if any((u.get('email') or '').lower() == email for u in users):
            return jsonify({'error': 'Email zaten kayıtlı'}), 409
        payload = {
            'email': email, 'name': name, 'surname': surname, 'phone': phone,
            'password_hash': hash_pw(password), 'role': role,
            'is_active': _bool(data.get('is_active'), True),
            'is_allowed': _bool(data.get('is_allowed'), True),
            'show_panel_help': _bool(data.get('show_panel_help'), False),
            'new_panel': _bool(data.get('new_panel'), False),
            'personnel': _bool(data.get('personnel'), False)
        }
        if get_db():
            if not _db_add_user(payload):
                return jsonify({'error': 'Kullanıcı DB kaydı yapılamadı'}), 500
            return jsonify({'ok': True, 'users': _get_all_users_public()})
        fallback = _fallback_users()
        fallback.append(payload)
        _save_fallback_users(fallback)
        return jsonify({'ok': True, 'users': _get_all_users_public()})

    parts = path.split('/')
    if len(parts) >= 4:
        email = unquote(parts[3])

        if len(parts) == 4 and request.method == 'DELETE':
            if get_db():
                _db_delete_user(email)
                return jsonify({'ok': True, 'users': _get_all_users_public()})
            users = [u for u in _fallback_users() if (u.get('email') or '').lower() != email.lower()]
            _save_fallback_users(users)
            return jsonify({'ok': True, 'users': _get_all_users_public()})

        if len(parts) == 4 and request.method in ('PUT', 'PATCH'):
            data = request.get_json(silent=True) or {}
            fields = {}
            for k in ('name', 'surname', 'phone', 'role'):
                if k in data:
                    fields[k] = data.get(k) or ''
            for k in ('is_active', 'is_allowed', 'show_panel_help', 'new_panel', 'personnel'):
                if k in data:
                    fields[k] = _bool(data.get(k), False)
            if data.get('password_apply') and data.get('password'):
                if len(data.get('password')) < 6:
                    return jsonify({'error': 'Şifre en az 6 karakter olmalı'}), 400
                fields['password_hash'] = hash_pw(data.get('password'))
            if get_db():
                _db_patch_user(email, **fields)
                return jsonify({'ok': True, 'users': _get_all_users_public()})
            users = _fallback_users()
            for u in users:
                if (u.get('email') or '').lower() == email.lower():
                    u.update(fields)
            _save_fallback_users(users)
            return jsonify({'ok': True, 'users': _get_all_users_public()})

        if len(parts) == 5 and parts[4] == 'role' and request.method == 'POST':
            data = request.get_json(silent=True) or {}
            role = data.get('role') or 'viewer'
            if get_db():
                _db_patch_user(email, role=role)
                return jsonify({'ok': True, 'users': _get_all_users_public()})
            users = _fallback_users()
            for u in users:
                if (u.get('email') or '').lower() == email.lower():
                    u['role'] = role
            _save_fallback_users(users)
            return jsonify({'ok': True, 'users': _get_all_users_public()})

        if len(parts) == 5 and parts[4] == 'reset' and request.method == 'POST':
            data = request.get_json(silent=True) or {}
            password = data.get('password') or ''
            if not password or len(password) < 6:
                return jsonify({'error': 'Şifre en az 6 karakter olmalı'}), 400
            if get_db():
                _db_patch_user(email, password_hash=hash_pw(password))
                return jsonify({'ok': True})
            users = _fallback_users()
            for u in users:
                if (u.get('email') or '').lower() == email.lower():
                    u['password_hash'] = hash_pw(password)
            _save_fallback_users(users)
            return jsonify({'ok': True})

        if len(parts) == 5 and parts[4] in ('active', 'allow') and request.method == 'POST':
            data = request.get_json(silent=True) or {}
            value = _bool(data.get('value'), True)
            key = 'is_active' if parts[4] == 'active' else 'is_allowed'
            if get_db():
                _db_patch_user(email, **{key: value})
                return jsonify({'ok': True, 'users': _get_all_users_public()})
            users = _fallback_users()
            for u in users:
                if (u.get('email') or '').lower() == email.lower():
                    u[key] = value
            _save_fallback_users(users)
            return jsonify({'ok': True, 'users': _get_all_users_public()})

        if len(parts) == 5 and parts[4] == '2fa-reset' and request.method == 'POST':
            if get_db():
                _db_2fa_reset(email)
                return jsonify({'ok': True, 'users': _get_all_users_public()})
            users = _fallback_users()
            import datetime as _dt
            for u in users:
                if (u.get('email') or '').lower() == email.lower():
                    u['two_factor_reset_at'] = _dt.datetime.utcnow().isoformat()
            _save_fallback_users(users)
            return jsonify({'ok': True, 'users': _get_all_users_public()})

    return None


password_reset_flow.install(
    app,
    get_db=get_db,
    hash_pw=hash_pw,
    read_logs=read_logs,
    write_logs=write_logs
)
