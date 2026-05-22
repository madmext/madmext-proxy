from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
import json
import threading
from datetime import datetime

app = Flask(__name__, static_folder='.')
CORS(app)

META_TOKEN = os.environ.get('META_TOKEN', '')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY', '')
GA4_PROPERTY_ID = os.environ.get('GA4_PROPERTY_ID', '')
GA4_REFRESH_TOKEN = os.environ.get('GA4_REFRESH_TOKEN', '')
GA4_CLIENT_ID = os.environ.get('GA4_CLIENT_ID', '')
GA4_CLIENT_SECRET = os.environ.get('GA4_CLIENT_SECRET', '')

LOG_FILE = 'madmext_logs.json'
log_lock = threading.Lock()

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
    return send_from_directory('.', 'index.html')

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
            json=data.get('body', {})
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
    data = request.json
    endpoint = data['endpoint']
    params = {**data.get('params', {}), 'access_token': META_TOKEN}
    method = data.get('method', 'GET')
    url = f"https://graph.facebook.com/v19.0/{endpoint}"
    if method == 'POST':
        r = requests.post(url, params=params)
    else:
        r = requests.get(url, params=params)
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


import xml.etree.ElementTree as ET

TICIMAX_KEY = os.environ.get('TICIMAX_KEY', '')
TICIMAX_URL = os.environ.get('TICIMAX_URL', 'https://www.madmext.com')

def ticimax_soap(action, body_inner):
    """Ticimax SOAP API çağrısı"""
    soap = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <{action} xmlns="http://tempuri.org/">
      <yetki_kodu>{TICIMAX_KEY}</yetki_kodu>
      {body_inner}
    </{action}>
  </soap:Body>
</soap:Envelope>'''
    r = requests.post(
        f"{TICIMAX_URL}/servis/ticimax.svc",
        data=soap.encode('utf-8'),
        headers={'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': f'http://tempuri.org/ITicimaxServis/{action}'},
        timeout=30
    )
    return r.text

def parse_ticimax_products(xml_text):
    """Ticimax ürün XML yanıtını parse et"""
    try:
        root = ET.fromstring(xml_text)
        ns = {'s': 'http://schemas.xmlsoap.org/soap/envelope/',
              'a': 'http://tempuri.org/',
              'b': 'http://schemas.datacontract.org/2004/07/Ticimax.Model'}
        products = []
        for p in root.iter():
            tag = p.tag.split('}')[-1] if '}' in p.tag else p.tag
            if tag in ['UrunModel', 'Urun', 'urun']:
                prod = {}
                for child in p:
                    ctag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    prod[ctag.lower()] = child.text or ''
                if prod:
                    products.append({
                        'id': prod.get('id', prod.get('urunid', '')),
                        'title': prod.get('adi', prod.get('ad', prod.get('urunadi', ''))),
                        'name': prod.get('adi', prod.get('ad', '')),
                        'stok_kodu': prod.get('stokkodu', prod.get('stok_kodu', '')),
                        'stok': int(prod.get('stok', prod.get('stokmiktari', 0)) or 0),
                        'fiyat': float(prod.get('fiyat', prod.get('satisfiyati', 0)) or 0),
                        'resim': prod.get('resim', prod.get('resimurl', prod.get('gorselurl', ''))),
                        'kategori': prod.get('kategori', prod.get('kategoriadi', 'Diğer')),
                        'aktif': prod.get('aktif', 'true').lower() == 'true',
                        'yayin_tarihi': prod.get('eklemetarihi', prod.get('yayintarihi', '')),
                        'marka': prod.get('marka', prod.get('markaadi', '')),
                    })
        return products
    except Exception as e:
        return []

@app.route('/ticimax/products', methods=['GET'])
def ticimax_products():
    if not TICIMAX_KEY:
        return jsonify({'error': 'TICIMAX_KEY eksik. Railway Variables ekle.'})
    try:
        all_products = []
        page = 1
        while True:
            xml = ticimax_soap('UrunListele', f'<sayfa_no>{page}</sayfa_no><sayfa_satir_sayisi>500</sayfa_satir_sayisi>')
            products = parse_ticimax_products(xml)
            if not products:
                break
            all_products.extend(products)
            if len(products) < 500:
                break
            page += 1
            if page > 20:  # Max 10K ürün (20*500)
                break
        return jsonify({'products': all_products, 'total': len(all_products)})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/ticimax/orders', methods=['GET'])
def ticimax_orders():
    if not TICIMAX_KEY:
        return jsonify({'error': 'TICIMAX_KEY eksik'})
    try:
        from datetime import datetime, timedelta
        date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT00:00:00')
        date_to = datetime.now().strftime('%Y-%m-%dT23:59:59')
        xml = ticimax_soap('SiparisListele',
            f'<baslangic_tarihi>{date_from}</baslangic_tarihi><bitis_tarihi>{date_to}</bitis_tarihi><sayfa_no>1</sayfa_no><sayfa_satir_sayisi>1000</sayfa_satir_sayisi>')
        # Basit parse - sipariş items
        root = ET.fromstring(xml)
        orders = []
        for o in root.iter():
            tag = o.tag.split('}')[-1] if '}' in o.tag else o.tag
            if tag in ['SiparisModel', 'Siparis', 'siparis']:
                order = {'items': []}
                for child in o:
                    ctag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if ctag.lower() in ['urunler', 'siparisdetay', 'items']:
                        for item in child:
                            item_data = {}
                            for ic in item:
                                ictag = ic.tag.split('}')[-1] if '}' in ic.tag else ic.tag
                                item_data[ictag.lower()] = ic.text or ''
                            if item_data:
                                order['items'].append({
                                    'urun_id': item_data.get('urunid', item_data.get('urun_id', '')),
                                    'stok_kodu': item_data.get('stokkodu', ''),
                                    'adet': int(item_data.get('adet', item_data.get('miktar', 1)) or 1)
                                })
                orders.append(order)
        return jsonify({'orders': orders, 'total': len(orders)})
    except Exception as e:
        return jsonify({'error': str(e), 'orders': []})

@app.route('/ticimax/test', methods=['GET'])
def ticimax_test():
    """Bağlantı testi"""
    if not TICIMAX_KEY:
        return jsonify({'ok': False, 'error': 'TICIMAX_KEY eksik'})
    try:
        xml = ticimax_soap('UrunListele', '<sayfa_no>1</sayfa_no><sayfa_satir_sayisi>1</sayfa_satir_sayisi>')
        return jsonify({'ok': True, 'response_length': len(xml), 'preview': xml[:200]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/claude', methods=['POST'])
def claude_proxy():
    data = request.json
    r = requests.post('https://api.anthropic.com/v1/messages',
        headers={'x-api-key': ANTHROPIC_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
        json=data)
    return jsonify(r.json())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
