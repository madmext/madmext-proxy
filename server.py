from flask import request, jsonify, session
from urllib.parse import unquote
from app import app, get_db, hash_pw, read_logs, write_logs
import password_reset_flow


def _is_admin():
    return session.get('user_role') == 'admin'


def _admin_required():
    if not _is_admin():
        return jsonify({'error': 'Admin gerekli'}), 403
    return None


def _db_init_user_meta():
    conn = get_db()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
        cur.execute("ALTER TABLE mx_users ADD COLUMN IF NOT EXISTS is_allowed BOOLEAN DEFAULT TRUE")
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


def _db_users():
    conn = get_db()
    if not conn:
        return None
    _db_init_user_meta()
    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
              row_number() OVER (ORDER BY created_at, email) AS user_no,
              email,
              name,
              role,
              created_at,
              updated_at,
              last_login,
              login_count,
              COALESCE(is_active, TRUE) AS is_active,
              COALESCE(is_allowed, TRUE) AS is_allowed,
              two_factor_reset_at
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


def _db_add_user(email, name, pw_hash, role):
    conn = get_db()
    if not conn:
        return False
    _db_init_user_meta()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO mx_users(email,name,password_hash,role,is_active,is_allowed,updated_at)
            VALUES(%s,%s,%s,%s,TRUE,TRUE,NOW())
        """, (email, name, pw_hash, role))
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
        'role': 'role',
        'password_hash': 'password_hash',
        'is_active': 'is_active',
        'is_allowed': 'is_allowed'
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
    data = read_logs()
    return data.get('users') or []


def _save_fallback_users(users):
    data = read_logs()
    data['users'] = users
    write_logs(data)


def _fallback_public(users):
    out = []
    for i, u in enumerate(users, 1):
        out.append({
            'user_no': i,
            'email': u.get('email'),
            'name': u.get('name'),
            'role': u.get('role', 'viewer'),
            'created_at': u.get('created_at') or '',
            'updated_at': u.get('updated_at') or '',
            'last_login': u.get('last_login') or '',
            'login_count': u.get('login_count') or 0,
            'is_active': u.get('is_active', True),
            'is_allowed': u.get('is_allowed', True),
            'two_factor_reset_at': u.get('two_factor_reset_at') or ''
        })
    return out


def _get_all_users_public():
    users = _db_users()
    if users is not None:
        return users
    return _fallback_public(_fallback_users())


@app.before_request
def _fresh_admin_users_override():
    path = request.path.rstrip('/') or '/'
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
        name = (data.get('name') or email).strip()
        password = data.get('password') or ''
        role = data.get('role') or 'viewer'
        if not email:
            return jsonify({'error': 'Email zorunlu'}), 400
        if not password or len(password) < 6:
            return jsonify({'error': 'Şifre en az 6 karakter olmalı'}), 400
        users = _get_all_users_public()
        if any((u.get('email') or '').lower() == email for u in users):
            return jsonify({'error': 'Email zaten kayıtlı'}), 409
        if get_db():
            if not _db_add_user(email, name, hash_pw(password), role):
                return jsonify({'error': 'Kullanıcı DB kaydı yapılamadı'}), 500
            return jsonify({'ok': True, 'users': _get_all_users_public()})
        fallback = _fallback_users()
        fallback.append({'email': email, 'name': name, 'password_hash': hash_pw(password), 'role': role, 'is_active': True, 'is_allowed': True})
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
            if 'name' in data:
                fields['name'] = data.get('name') or email
            if 'role' in data:
                fields['role'] = data.get('role') or 'viewer'
            if 'is_active' in data:
                fields['is_active'] = bool(data.get('is_active'))
            if 'is_allowed' in data:
                fields['is_allowed'] = bool(data.get('is_allowed'))
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
            value = bool(data.get('value'))
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
