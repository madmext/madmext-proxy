from flask import Flask, request, jsonify, send_from_directory, session, redirect
from flask_cors import CORS
import requests
import os
import json
import threading
import hashlib
import secrets
from datetime import datetime

app = Flask(__name__, static_folder='.')
CORS(app, supports_credentials=True)

app.secret_key = os.environ.get('SECRET_KEY', 'madmext-secret-2026-change-this')

META_TOKEN = os.environ.get('META_TOKEN', '')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY', '')
GA4_PROPERTY_ID = os.environ.get('GA4_PROPERTY_ID', '')
GA4_REFRESH_TOKEN = os.environ.get('GA4_REFRESH_TOKEN', '')
GA4_CLIENT_ID = os.environ.get('GA4_CLIENT_ID', '')
GA4_CLIENT_SECRET = os.environ.get('GA4_CLIENT_SECRET', '')

LOG_FILE = 'madmext_logs.json'
log_lock = threading.Lock()

# ── KULLANICI SİSTEMİ ─────────────────────────────────────────────────────
# Kullanıcılar USERS_DATA env variable'da JSON olarak tutulur
# Format: [{"email":"admin@x.com","password_hash":"...","role":"admin","name":"Admin"}]
# Yoksa varsayılan admin oluştur

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_users():
    try:
        raw = os.environ.get('USERS_DATA', '')
        if raw:
            return json.loads(raw)
    except:
        pass
    # Varsayılan admin
    return [{
        "email": os.environ.get('ADMIN_EMAIL', 'admin@madmext.com'),
        "password_hash": hash_password(os.environ.get('ADMIN_PASSWORD', 'madmext2026')),
        "role": "admin",
        "name": "Admin"
    }]

def save_users(users):
    # Kullanıcıları log dosyasına yaz (env var dinamik değiştirilemez)
    current = read_logs()
    current['users'] = users
    write_logs(current)

def load_users_from_logs():
    # Önce log dosyasından bak (admin değişiklik yaptıysa)
    current = read_logs()
    if 'users' in current and current['users']:
        return current['users']
    return get_users()

def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_email'):
            return jsonify({'error': 'Yetkisiz erişim', 'redirect': '/login'}), 401
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_email'):
            return jsonify({'error': 'Yetkisiz erişim'}), 401
        if session.get('user_role') != 'admin':
            return jsonify({'error': 'Admin yetkisi gerekli'}), 403
        return f(*args, **kwargs)
    return decorated

# ── LOG SİSTEMİ ───────────────────────────────────────────────────────────

def read_logs():
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {'budgetLog': [], 'taskLog': [], 'actionLog': [], 'resetRequests': [], 'users': []}

def write_logs(data):
    with log_lock:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def get_ga4_token():
    r = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': GA4_CLIENT_ID,
        'client_secret': GA4_CLIENT_SECRET,
        'refresh_token': GA4_REFRESH_TOKEN,
        'grant_type': 'refresh_token'
    })
    return r.json().get('access_token')

# ── STATIC FILES ──────────────────────────────────────────────────────────

@app.route('/')
def home():
    if not session.get('user_email'):
        return send_from_directory('.', 'login.html')
    return send_from_directory('.', 'index.html')

@app.route('/login')
def login_page():
    if session.get('user_email'):
        return redirect('/')
    return send_from_directory('.', 'login.html')

@app.route('/theme.css')
def serve_theme():
    try:
        return send_from_directory('.', 'theme.css')
    except:
        return ':root{}', 200, {'Content-Type': 'text/css'}

@app.route('/proxy-xml', methods=['GET'])
def proxy_xml():
    url = request.args.get('url', '')
    if not url: return 'URL gerekli', 400
    try:
        r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        return r.text, 200, {'Content-Type': 'application/xml; charset=utf-8'}
    except Exception as e:
        return str(e), 500

@app.route('/modules/<path:filename>')
def serve_module(filename):
    if not session.get('user_email'):
        return jsonify({'error': 'Yetkisiz'}), 401
    return send_from_directory('modules', filename)

@app.route('/modules/shared.js')
def serve_shared():
    return send_from_directory('modules', 'shared.js')

@app.route('/madmext-ads.html')
def serve_old():
    return send_from_directory('.', 'index.html')

# ── AUTH ROUTES ───────────────────────────────────────────────────────────

@app.route('/auth/login', methods=['POST'])
def auth_login():
    data = request.json
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    users = load_users_from_logs()
    pw_hash = hash_password(password)
    user = next((u for u in users if u['email'].lower() == email and u['password_hash'] == pw_hash), None)
    if not user:
        return jsonify({'error': 'Email veya şifre hatalı'}), 401
    session['user_email'] = user['email']
    session['user_name'] = user.get('name', email)
    session['user_role'] = user.get('role', 'user')
    session.permanent = True
    return jsonify({
        'ok': True,
        'user': {'email': user['email'], 'name': user.get('name'), 'role': user.get('role')}
    })

@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/auth/me', methods=['GET'])
def auth_me():
    if not session.get('user_email'):
        return jsonify({'error': 'Giriş yapılmamış'}), 401
    return jsonify({
        'email': session['user_email'],
        'name': session.get('user_name'),
        'role': session.get('user_role')
    })

@app.route('/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json
    email = (data.get('email') or '').strip().lower()
    message = data.get('message') or 'Şifremi unuttum'
    users = load_users_from_logs()
    user_exists = any(u['email'].lower() == email for u in users)
    current = read_logs()
    current.setdefault('resetRequests', []).insert(0, {
        'email': email,
        'message': message,
        'time': datetime.utcnow().isoformat(),
        'status': 'pending',
        'user_exists': user_exists
    })
    current['resetRequests'] = current['resetRequests'][:100]
    write_logs(current)
    return jsonify({'ok': True, 'message': 'Talebiniz yöneticiye iletildi.'})

# ── KULLANICI YÖNETİMİ (Admin) ────────────────────────────────────────────

@app.route('/admin/users', methods=['GET'])
@require_admin
def admin_get_users():
    users = load_users_from_logs()
    safe = [{'email': u['email'], 'name': u.get('name'), 'role': u.get('role', 'user')} for u in users]
    return jsonify(safe)

@app.route('/admin/users', methods=['POST'])
@require_admin
def admin_add_user():
    data = request.json
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    name = data.get('name') or email
    role = data.get('role') or 'user'
    if not email or not password:
        return jsonify({'error': 'Email ve şifre zorunlu'}), 400
    users = load_users_from_logs()
    if any(u['email'].lower() == email for u in users):
        return jsonify({'error': 'Bu email zaten kayıtlı'}), 409
    users.append({'email': email, 'password_hash': hash_password(password), 'name': name, 'role': role})
    save_users(users)
    return jsonify({'ok': True})

@app.route('/admin/users/<email>', methods=['DELETE'])
@require_admin
def admin_delete_user(email):
    if email.lower() == session['user_email'].lower():
        return jsonify({'error': 'Kendi hesabınızı silemezsiniz'}), 400
    users = load_users_from_logs()
    users = [u for u in users if u['email'].lower() != email.lower()]
    save_users(users)
    return jsonify({'ok': True})

@app.route('/admin/users/<email>/reset', methods=['POST'])
@require_admin
def admin_reset_password(email):
    data = request.json
    new_password = data.get('password') or ''
    if not new_password:
        return jsonify({'error': 'Yeni şifre zorunlu'}), 400
    users = load_users_from_logs()
    for u in users:
        if u['email'].lower() == email.lower():
            u['password_hash'] = hash_password(new_password)
            break
    save_users(users)
    return jsonify({'ok': True})

@app.route('/admin/users/<email>/role', methods=['POST'])
@require_admin
def admin_change_role(email):
    data = request.json
    new_role = data.get('role') or 'user'
    users = load_users_from_logs()
    for u in users:
        if u['email'].lower() == email.lower():
            u['role'] = new_role
            break
    save_users(users)
    return jsonify({'ok': True})

@app.route('/admin/reset-requests', methods=['GET'])
@require_admin
def admin_reset_requests():
    current = read_logs()
    return jsonify(current.get('resetRequests', []))

@app.route('/admin/reset-requests/<int:idx>/resolve', methods=['POST'])
@require_admin
def admin_resolve_request(idx):
    current = read_logs()
    reqs = current.get('resetRequests', [])
    if 0 <= idx < len(reqs):
        reqs[idx]['status'] = 'resolved'
        reqs[idx]['resolved_by'] = session['user_email']
        reqs[idx]['resolved_at'] = datetime.utcnow().isoformat()
    write_logs(current)
    return jsonify({'ok': True})

# ── GA4 ───────────────────────────────────────────────────────────────────

@app.route('/ga4', methods=['POST'])
@require_auth
def ga4_proxy():
    try:
        data = request.json
        token = get_ga4_token()
        if not token:
            return jsonify({'error': 'GA4 token alınamadı'})
        report_type = data.get('type', 'runReport')
        url = f'https://analyticsdata.googleapis.com/v1beta/properties/{GA4_PROPERTY_ID}:{report_type}'
        r = requests.post(url,
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json=data.get('body', {}))
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)})

# ── LOGS ──────────────────────────────────────────────────────────────────

@app.route('/logs', methods=['GET'])
@require_auth
def get_logs():
    current = read_logs()
    return jsonify({
        'budgetLog': current.get('budgetLog', []),
        'taskLog': current.get('taskLog', []),
        'actionLog': current.get('actionLog', [])
    })

@app.route('/logs/save', methods=['POST'])
@require_auth
def save_logs():
    data = request.json
    current = read_logs()
    if 'budgetLog' in data: current['budgetLog'] = data['budgetLog']
    if 'taskLog' in data: current['taskLog'] = data['taskLog']
    write_logs(current)
    return jsonify({'ok': True})

@app.route('/logs/action', methods=['POST'])
@require_auth
def log_action_route():
    data = request.json
    current = read_logs()
    current.setdefault('actionLog', []).insert(0, {**data, 'serverTime': datetime.utcnow().isoformat()})
    current['actionLog'] = current['actionLog'][:500]
    write_logs(current)
    return jsonify({'ok': True})

# ── META ──────────────────────────────────────────────────────────────────

@app.route('/api', methods=['POST'])
@require_auth
def meta_proxy():
    import json as _json
    data = request.json
    endpoint = data['endpoint']
    raw_params = data.get('params', {})
    method = data.get('method', 'GET')
    url = f"https://graph.facebook.com/v19.0/{endpoint}"

    param_list = [('access_token', META_TOKEN)]
    for k, v in raw_params.items():
        if k == 'action_attribution_windows' and isinstance(v, str):
            try:
                arr = _json.loads(v)
                for item in arr:
                    param_list.append((k + '[]', item))
            except:
                param_list.append((k, v))
        elif k == 'time_range' and isinstance(v, str):
            param_list.append((k, v))
        else:
            param_list.append((k, v))

    if method == 'POST':
        r = requests.post(url, params=param_list)
    else:
        r = requests.get(url, params=param_list)

    result = r.json()
    if method == 'POST' and (result.get('success') or result.get('id')):
        try:
            current = read_logs()
            current.setdefault('actionLog', []).insert(0, {
                'type': 'budget_change', 'endpoint': endpoint,
                'params': {k: v for k, v in data.get('params', {}).items() if k != 'access_token'},
                'user': session.get('user_email', 'unknown'),
                'serverTime': datetime.utcnow().isoformat()
            })
            current['actionLog'] = current['actionLog'][:500]
            write_logs(current)
        except:
            pass
    return jsonify(result)

# ── CLAUDE ────────────────────────────────────────────────────────────────

@app.route('/claude', methods=['POST'])
@require_auth
def claude_proxy():
    data = request.json
    r = requests.post('https://api.anthropic.com/v1/messages',
        headers={'x-api-key': ANTHROPIC_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
        json=data)
    return jsonify(r.json())

# ── DAILY REPORT (Cron tetikler) ──────────────────────────────────────────

@app.route('/cron/daily-report', methods=['GET', 'POST'])
def daily_report():
    cron_key = request.args.get('key') or (request.json or {}).get('key')
    expected = os.environ.get('CRON_KEY', 'madmext-cron-2026')
    if cron_key != expected:
        return jsonify({'error': 'Yetkisiz'}), 401
    current = read_logs()
    report = {
        'date': datetime.utcnow().strftime('%Y-%m-%d'),
        'time': datetime.utcnow().isoformat(),
        'budgetChanges': len(current.get('budgetLog', [])),
        'pendingTasks': sum(1 for t in current.get('taskLog', []) if not t.get('done')),
        'generated': True
    }
    current.setdefault('dailyReports', []).insert(0, report)
    current['dailyReports'] = current['dailyReports'][:30]
    write_logs(current)
    return jsonify({'ok': True, 'report': report})

@app.route('/reports/daily', methods=['GET'])
@require_auth
def get_daily_reports():
    current = read_logs()
    return jsonify(current.get('dailyReports', []))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
