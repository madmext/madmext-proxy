from flask import request, jsonify, session
from app import (
    app,
    get_db,
    hash_pw,
    read_logs,
    write_logs,
    db_get_users,
    db_upsert_user,
    db_delete,
    db_update_role,
    db_update_pw,
)
import password_reset_flow


def _is_admin():
    return session.get('user_role') == 'admin'


def _admin_required():
    if not _is_admin():
        return jsonify({'error': 'Admin gerekli'}), 403
    return None


def _fallback_users():
    data = read_logs()
    return data.get('users') or []


def _save_fallback_users(users):
    data = read_logs()
    data['users'] = users
    write_logs(data)


def _public_users(users):
    return [{'email': u.get('email'), 'name': u.get('name'), 'role': u.get('role', 'viewer')} for u in users]


@app.before_request
def _fresh_admin_users_override():
    path = request.path.rstrip('/') or '/'
    if not path.startswith('/admin/users'):
        return None

    r = _admin_required()
    if r:
        return r

    if path == '/admin/users' and request.method == 'GET':
        users = db_get_users()
        if users is None:
            users = _fallback_users()
        return jsonify(_public_users(users))

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
        pw_hash = hash_pw(password)

        users = db_get_users()
        if users is not None:
            if any((u.get('email') or '').lower() == email for u in users):
                return jsonify({'error': 'Email zaten kayıtlı'}), 409
            ok = db_upsert_user(email, name, pw_hash, role)
            if not ok:
                return jsonify({'error': 'Kullanıcı DB kaydı yapılamadı'}), 500
            users = db_get_users() or []
            return jsonify({'ok': True, 'users': _public_users(users)})

        users = _fallback_users()
        if any((u.get('email') or '').lower() == email for u in users):
            return jsonify({'error': 'Email zaten kayıtlı'}), 409
        users.append({'email': email, 'name': name, 'password_hash': pw_hash, 'role': role})
        _save_fallback_users(users)
        return jsonify({'ok': True, 'users': _public_users(users)})

    parts = path.split('/')
    # /admin/users/<email>
    if len(parts) >= 4:
        email = parts[3]

        if len(parts) == 4 and request.method == 'DELETE':
            users = db_get_users()
            if users is not None:
                db_delete(email)
                users = db_get_users() or []
                return jsonify({'ok': True, 'users': _public_users(users)})
            users = [u for u in _fallback_users() if (u.get('email') or '').lower() != email.lower()]
            _save_fallback_users(users)
            return jsonify({'ok': True, 'users': _public_users(users)})

        if len(parts) == 5 and parts[4] == 'role' and request.method == 'POST':
            data = request.get_json(silent=True) or {}
            role = data.get('role') or 'viewer'
            users = db_get_users()
            if users is not None:
                db_update_role(email, role)
                users = db_get_users() or []
                return jsonify({'ok': True, 'users': _public_users(users)})
            users = _fallback_users()
            for u in users:
                if (u.get('email') or '').lower() == email.lower():
                    u['role'] = role
            _save_fallback_users(users)
            return jsonify({'ok': True, 'users': _public_users(users)})

        if len(parts) == 5 and parts[4] == 'reset' and request.method == 'POST':
            data = request.get_json(silent=True) or {}
            password = data.get('password') or ''
            if not password or len(password) < 6:
                return jsonify({'error': 'Şifre en az 6 karakter olmalı'}), 400
            pw_hash = hash_pw(password)
            users = db_get_users()
            if users is not None:
                db_update_pw(email, pw_hash)
                return jsonify({'ok': True})
            users = _fallback_users()
            for u in users:
                if (u.get('email') or '').lower() == email.lower():
                    u['password_hash'] = pw_hash
            _save_fallback_users(users)
            return jsonify({'ok': True})

    return None


password_reset_flow.install(
    app,
    get_db=get_db,
    hash_pw=hash_pw,
    read_logs=read_logs,
    write_logs=write_logs
)
