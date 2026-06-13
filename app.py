from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import requests
import os
import json
import threading
import hashlib
from datetime import datetime

try:
    import psycopg2
    import psycopg2.extras
    HAS_PG = True
except ImportError:
    HAS_PG = False

app = Flask(__name__, static_folder='.')
app.secret_key = os.environ.get('SECRET_KEY', 'madmext-default-key-2026')
from datetime import timedelta
app.permanent_session_lifetime = timedelta(days=30)
CORS(app, supports_credentials=True)

META_TOKEN = os.environ.get('META_TOKEN', '')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY', '')
GA4_PROPERTY_ID = os.environ.get('GA4_PROPERTY_ID', '')
GA4_REFRESH_TOKEN = os.environ.get('GA4_REFRESH_TOKEN', '')
GA4_CLIENT_ID = os.environ.get('GA4_CLIENT_ID', '')
GA4_CLIENT_SECRET = os.environ.get('GA4_CLIENT_SECRET', '')

LOG_FILE = 'madmext_logs.json'
log_lock = threading.Lock()

# ── In-memory kullanıcı cache (restart'ta USERS_JSON'dan restore edilir) ──
_users_cache = None
_users_lock = threading.Lock()

# ── GA4 token cache — 50 dakika geçerli, her istekte OAuth çağrısı yapılmaz ──
_ga4_token_cache = {'token': None, 'expires_at': 0}
_ga4_token_lock = threading.Lock()

def read_logs():
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {'budgetLog': [], 'taskLog': [], 'actionLog': []}

def write_logs(data):
    with log_lock:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def get_ga4_token():
    import time
    with _ga4_token_lock:
        now = time.time()
        if _ga4_token_cache['token'] and now < _ga4_token_cache['expires_at']:
            return _ga4_token_cache['token']
        try:
            r = requests.post('https://oauth2.googleapis.com/token', data={
                'client_id': GA4_CLIENT_ID,
                'client_secret': GA4_CLIENT_SECRET,
                'refresh_token': GA4_REFRESH_TOKEN,
                'grant_type': 'refresh_token'
            }, timeout=10)
            token = r.json().get('access_token')
            if token:
                _ga4_token_cache['token'] = token
                _ga4_token_cache['expires_at'] = now + 2900  # 50 dk cache
            return token
        except Exception as e:
            print('GA4 token hata:', e)
            return None

# ── STATIC FILES ──────────────────────────────────────────────────────────


# ── PostgreSQL ───────────────────────────────────────────────────────
def get_db():
    url = os.environ.get('DATABASE_URL','')
    if not url or not HAS_PG: return None
    try:
        if url.startswith('postgres://'): url = url.replace('postgres://','postgresql://',1)
        return psycopg2.connect(url, sslmode='require')
    except Exception as e:
        print('DB error:', e); return None

def init_db():
    conn = get_db()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mx_users (
                email TEXT PRIMARY KEY,
                name TEXT,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'viewer',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit(); cur.close(); conn.close()
    except Exception as e: print('init_db:', e)

def db_get_users():
    conn = get_db()
    if not conn: return None
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT email,name,password_hash,role FROM mx_users ORDER BY created_at')
        rows = [dict(r) for r in cur.fetchall()]
        cur.close(); conn.close()
        return rows
    except Exception as e: print('db_get_users:', e); return None

def db_upsert_user(email, name, pw_hash, role):
    conn = get_db()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO mx_users(email,name,password_hash,role) VALUES(%s,%s,%s,%s) ON CONFLICT(email) DO UPDATE SET name=%s,role=%s',
            (email,name,pw_hash,role,name,role)
        )
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e: print('db_upsert:', e); return False

def db_delete(email):
    conn = get_db()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM mx_users WHERE email=%s',(email,))
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e: print('db_delete:', e); return False

def db_update_role(email, role):
    conn = get_db()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute('UPDATE mx_users SET role=%s WHERE email=%s',(role,email))
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e: print('db_update_role:', e); return False

def db_update_pw(email, pw_hash):
    conn = get_db()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute('UPDATE mx_users SET password_hash=%s WHERE email=%s',(pw_hash,email))
        conn.commit(); cur.close(); conn.close(); return True
    except Exception as e: print('db_update_pw:', e); return False

# DB init + ilk admin
try:
    init_db()
    existing = db_get_users()
    if existing is not None and len(existing) == 0:
        db_upsert_user(
            os.environ.get('ADMIN_EMAIL','admin@madmext.com'),
            'Admin',
            hashlib.sha256(os.environ.get('ADMIN_PASSWORD','madmext2026').encode()).hexdigest(),
            'admin'
        )
except Exception as e: print('DB init error:', e)

def hash_pw(p): return hashlib.sha256(p.encode()).hexdigest()

def is_admin():
    """SECRET_KEY yoksa herkes admin, varsa session'dan kontrol et"""
    if not os.environ.get('SECRET_KEY'):
        return True
    # Session varsa role kontrol et
    role = session.get('user_role')
    if role:
        return role == 'admin'
    # Session yoksa - eğer login sayfası varsa 403, yoksa admin kabul et
    return not os.path.exists('login.html')

def require_admin():
    """Admin değilse 403 döndür, admin ise None"""
    if not is_admin():
        return jsonify({'error':'Admin gerekli'}), 403
    return None

def _default_admin():
    return [{'email':os.environ.get('ADMIN_EMAIL','admin@madmext.com'),
             'password_hash':hash_pw(os.environ.get('ADMIN_PASSWORD','madmext2026')),
             'role':'admin','name':'Admin'}]

def _load_users_from_env():
    """USERS_JSON env var'dan kullanıcıları yükle"""
    import base64
    uj = os.environ.get('USERS_JSON','')
    if uj:
        try:
            u = json.loads(base64.b64decode(uj).decode())
            if u: return u
        except: pass
    return None

def _users_to_json_b64(users):
    """Kullanıcı listesini base64 JSON'a çevir"""
    import base64
    return base64.b64encode(json.dumps(users, ensure_ascii=False).encode()).decode()

def get_users():
    global _users_cache
    # 1. In-memory cache — en hızlı, DB bağlantısı gerektirmez
    with _users_lock:
        if _users_cache is not None:
            return list(_users_cache)
    # 2. PostgreSQL — sadece cache boşsa sorgula
    pg = db_get_users()
    if pg is not None:
        result = pg if pg else _default_admin()
        with _users_lock:
            _users_cache = list(result)
        return result
    # 3. USERS_JSON env var
    env_users = _load_users_from_env()
    if env_users:
        with _users_lock:
            _users_cache = list(env_users)
        return env_users
    # 4. Dosya
    try:
        logs = read_logs()
        if logs.get('users'):
            with _users_lock:
                _users_cache = list(logs['users'])
            return logs['users']
    except: pass
    # 5. Default admin
    default = _default_admin()
    with _users_lock:
        _users_cache = list(default)
    return default

def save_users(users):
    """Kullanıcıları cache'e ve dosyaya kaydet"""
    global _users_cache
    with _users_lock:
        _users_cache = list(users)
    # Dosyaya da kaydet (restart'a kadar geçerli)
    try:
        current = read_logs()
        current['users'] = users
        write_logs(current)
    except: pass
    return _users_to_json_b64(users)

@app.route('/')
@app.route('/ads')
@app.route('/strateji')
@app.route('/optimizasyon')
@app.route('/hedef-kitle')
@app.route('/tasarim')
@app.route('/raporlar')
@app.route('/gorevler')
@app.route('/olustur')
@app.route('/ayarlar')
@app.route('/kullanicilar')
@app.route('/ai')
@app.route('/google-ads')
@app.route('/seo')
def home():
    if os.environ.get('SECRET_KEY') and not session.get('user_email'):
        return send_from_directory('.', 'login.html') if os.path.exists('login.html') else send_from_directory('.', 'index.html')
    return send_from_directory('.', 'index.html')

@app.route('/login')
def login_page():
    return send_from_directory('.', 'login.html') if os.path.exists('login.html') else send_from_directory('.', 'index.html')

@app.route('/auth/me')
def auth_me():
    # SECRET_KEY yoksa her zaman admin dön
    if not os.environ.get('SECRET_KEY'):
        return jsonify({'email':'admin@madmext.com','name':'Admin','role':'admin'})
    if not session.get('user_email'):
        return jsonify({'error':'Giris yapilmamis'}), 401
    return jsonify({'email':session['user_email'],'name':session.get('user_name'),'role':session.get('user_role','admin')})

@app.route('/auth/login', methods=['POST'])
def auth_login():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    users = get_users()
    user = next((u for u in users if u['email'].lower()==email and u['password_hash']==hash_pw(password)), None)
    if not user: return jsonify({'error':'Email veya şifre hatalı'}), 401
    session['user_email'] = user['email']
    session['user_name'] = user.get('name', email)
    session['user_role'] = user.get('role') or 'admin'
    session.permanent = True
    return jsonify({'ok':True,'user':{'email':user['email'],'name':user.get('name'),'role':user.get('role')}})

@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    session.clear()
    return jsonify({'ok':True})

@app.route('/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json or {}
    current = read_logs()
    current.setdefault('resetRequests',[]).insert(0,{
        'email':data.get('email',''), 'message':data.get('message','Şifremi unuttum'),
        'time':datetime.utcnow().isoformat(), 'status':'pending'
    })
    write_logs(current)
    return jsonify({'ok':True})

@app.route('/admin/users', methods=['GET'])
def admin_get_users():
    r = require_admin()
    if r: return r
    users = get_users()
    return jsonify([{'email':u['email'],'name':u.get('name'),'role':u.get('role','user')} for u in users])

@app.route('/admin/users', methods=['POST'])
def admin_add_user():
    r = require_admin()
    if r: return r
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    name = data.get('name', email)
    pw = hash_pw(data.get('password',''))
    role = data.get('role','viewer')
    if get_db():
        users = get_users()
        if any(u['email'].lower()==email for u in users): return jsonify({'error':'Email zaten kayitli'}), 409
        db_upsert_user(email, name, pw, role)
        return jsonify({'ok':True})
    users = get_users()
    if any(u['email'].lower()==email for u in users): return jsonify({'error':'Email zaten kayitli'}), 409
    users.append({'email':email,'password_hash':pw,'name':name,'role':role})
    uj = save_users(users)
    return jsonify({'ok':True,'users_json':uj})

@app.route('/admin/users/<email>', methods=['DELETE'])
def admin_delete_user(email):
    r = require_admin()
    if r: return r
    if get_db():
        db_delete(email)
        return jsonify({'ok':True})
    users = [u for u in get_users() if u['email'].lower()!=email.lower()]
    uj = save_users(users)
    return jsonify({'ok':True,'users_json':uj})

@app.route('/admin/users/<email>/reset', methods=['POST'])
def admin_reset_pw(email):
    r = require_admin()
    if r: return r
    data = request.json or {}
    pw = hash_pw(data.get('password',''))
    if get_db():
        db_update_pw(email, pw)
        return jsonify({'ok':True})
    users = get_users()
    for u in users:
        if u['email'].lower()==email.lower(): u['password_hash']=pw
    uj = save_users(users)
    return jsonify({'ok':True,'users_json':uj})

@app.route('/admin/users/<email>/role', methods=['POST'])
def admin_change_role(email):
    r = require_admin()
    if r: return r
    data = request.json or {}
    role = data.get('role','viewer')
    if get_db():
        db_update_role(email, role)
        return jsonify({'ok':True})
    users = get_users()
    for u in users:
        if u['email'].lower()==email.lower(): u['role']=role
    uj = save_users(users)
    return jsonify({'ok':True,'users_json':uj})

@app.route('/admin/reset-requests')
def admin_reset_requests():
    r = require_admin()
    if r: return r
    return jsonify(read_logs().get('resetRequests',[]))

@app.route('/admin/reset-requests/<int:idx>/resolve', methods=['POST'])
def resolve_request(idx):
    r = require_admin()
    if r: return r
    current = read_logs()
    reqs = current.get('resetRequests',[])
    if 0<=idx<len(reqs): reqs[idx]['status']='resolved'
    write_logs(current)
    return jsonify({'ok':True})

@app.route('/theme.css')
def serve_theme():
    try:
        return send_from_directory('.', 'theme.css')
    except:
        return ':root{}', 200, {'Content-Type': 'text/css'}

@app.route('/proxy-xml', methods=['GET'])
def proxy_xml():
    url = request.args.get('url','')
    if not url: return 'URL gerekli', 400
    try:
        r = requests.get(url, timeout=15, headers={'User-Agent':'Mozilla/5.0'})
        return r.text, 200, {'Content-Type':'application/xml; charset=utf-8'}
    except Exception as e:
        return str(e), 500

@app.route('/modules/<path:filename>')
def serve_module(filename):
    return send_from_directory('modules', filename)

@app.route('/madmext-ads.html')
def serve_old():
    # Eski URL'ye girenler için yönlendirme
    return send_from_directory('.', 'index.html')

# ── GA4 ───────────────────────────────────────────────────────────────────

@app.route('/ga4', methods=['POST'])
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
            json=data.get('body', {}),
            timeout=15
        )
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)})

# ── LOGS ──────────────────────────────────────────────────────────────────

@app.route('/logs', methods=['GET'])
def get_logs():
    return jsonify(read_logs())

@app.route('/logs/save', methods=['POST'])
def save_logs():
    data = request.json
    current = read_logs()
    if 'budgetLog' in data: current['budgetLog'] = data['budgetLog']
    if 'taskLog' in data: current['taskLog'] = data['taskLog']
    write_logs(current)
    return jsonify({'ok': True})

@app.route('/logs/action', methods=['POST'])
def log_action():
    data = request.json
    current = read_logs()
    current.setdefault('actionLog', []).insert(0, {**data, 'serverTime': datetime.utcnow().isoformat()})
    current['actionLog'] = current['actionLog'][:500]
    write_logs(current)
    return jsonify({'ok': True})

# ── META ──────────────────────────────────────────────────────────────────

@app.route('/api', methods=['POST'])
def meta_proxy():
    import json as _json
    data = request.json
    endpoint = data['endpoint']
    raw_params = data.get('params', {})
    method = data.get('method', 'GET')
    url = f"https://graph.facebook.com/v19.0/{endpoint}"

    # Parametreleri tuple listesi olarak hazırla (array params için)
    param_list = [('access_token', META_TOKEN)]
    for k, v in raw_params.items():
        if k == 'action_attribution_windows' and isinstance(v, str):
            # ["7d_click","1d_view"] formatını ayrı parametrelere böl
            try:
                arr = _json.loads(v)
                for item in arr:
                    param_list.append((k + '[]', item))
            except:
                param_list.append((k, v))
        elif k == 'time_range' and isinstance(v, str):
            # time_range JSON string olarak gitmeli — olduğu gibi bırak
            param_list.append((k, v))
        else:
            param_list.append((k, v))

    if method == 'POST':
        r = requests.post(url, params=param_list, timeout=20)
    else:
        r = requests.get(url, params=param_list, timeout=20)
    result = r.json()
    if method == 'POST' and (result.get('success') or result.get('id')):
        try:
            current = read_logs()
            current.setdefault('actionLog', []).insert(0, {
                'type': 'budget_change', 'endpoint': endpoint,
                'params': {k: v for k, v in data.get('params', {}).items() if k != 'access_token'},
                'serverTime': datetime.utcnow().isoformat()
            })
            current['actionLog'] = current['actionLog'][:500]
            write_logs(current)
        except: pass
    return jsonify(result)


# ── CLAUDE ────────────────────────────────────────────────────────────────

@app.route('/claude', methods=['POST'])
def claude_proxy():
    data = request.json
    try:
        r = requests.post('https://api.anthropic.com/v1/messages',
            headers={'x-api-key': ANTHROPIC_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
            json=data, timeout=60)
        return jsonify(r.json())
    except requests.Timeout:
        return jsonify({'error': {'message': 'Claude zaman aşımı (60s)'}}), 504
    except Exception as e:
        return jsonify({'error': {'message': str(e)}}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

