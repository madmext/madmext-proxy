from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os

app = Flask(__name__, static_folder='.')
CORS(app)

META_TOKEN = os.environ.get('META_TOKEN', '')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_KEY', '')

@app.route('/')
def home():
    return send_from_directory('.', 'madmext-ads.html')

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
    return jsonify(r.json())

@app.route('/claude', methods=['POST'])
def claude_proxy():
    data = request.json
    r = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': ANTHROPIC_KEY,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        },
        json=data
    )
    return jsonify(r.json())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
