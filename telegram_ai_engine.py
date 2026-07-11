"""Read-only Claude tool-use engine for Telegram Phase 2."""

import json
import os
import time
from collections import defaultdict, deque
from decimal import Decimal

import requests


TOOLS = [
    {'name': 'get_campaign_performance', 'description': 'Meta ve Google reklam kampanyalarının son performansını getirir.', 'input_schema': {'type': 'object', 'properties': {'days': {'type': 'integer', 'minimum': 1, 'maximum': 90}}}},
    {'name': 'get_ga4_summary', 'description': 'GA4 trafik özetini getirir.', 'input_schema': {'type': 'object', 'properties': {'days': {'type': 'integer', 'minimum': 1, 'maximum': 90}}}},
    {'name': 'get_trendyol_summary', 'description': 'Trendyol satış ve ürün performansı özetini getirir.', 'input_schema': {'type': 'object', 'properties': {'days': {'type': 'integer', 'minimum': 1, 'maximum': 90}}}},
    {'name': 'get_decision_queue', 'description': 'Salt okunur karar ve öneri kuyruğunu getirir.', 'input_schema': {'type': 'object', 'properties': {'status': {'type': 'string'}}}},
]


def _json(value):
    if isinstance(value, Decimal): return float(value)
    if hasattr(value, 'isoformat'): return value.isoformat()
    return str(value)


def split_telegram_message(text, limit=4096):
    text = str(text or '')
    if len(text) <= limit: return [text]
    chunks = []
    while text:
        cut = min(limit, len(text))
        if cut < len(text):
            boundary = max(text.rfind('\n', 0, cut), text.rfind(' ', 0, cut))
            if boundary > limit // 2: cut = boundary
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    return chunks


class TelegramAIEngine:
    def __init__(self, app, get_db, http_post=None, clock=None, ga4_token_getter=None):
        self.app, self.get_db = app, get_db
        self.http_post = http_post or requests.post
        self.clock = clock or time.time
        self.ga4_token_getter = ga4_token_getter
        self.memory_rate = defaultdict(deque)
        self.memory_usage = []
        self.api_key = (os.environ.get('ANTHROPIC_KEY') or os.environ.get('ANTHROPIC_API_KEY') or '').strip()
        self.model = os.environ.get('ANTHROPIC_MODEL', 'claude-sonnet-4-5-20250929')

    @staticmethod
    def split_message(text):
        return split_telegram_message(text)

    def _allowed(self, role):
        checker = self.app.extensions.get('mx_has_permission')
        if checker:
            conn = self.get_db()
            if conn:
                conn.close()
                return bool(checker(role, 'data.read'))
        return role in ('viewer','editor','admin','super_admin')

    def check_rate_limit(self, chat_id, limit=6, window=60):
        conn = self.get_db()
        if not conn:
            q = self.memory_rate[str(chat_id)]; now = self.clock()
            while q and q[0] <= now - window: q.popleft()
            if len(q) >= limit: return False
            q.append(now); return True
        try:
            cur = conn.cursor()
            cur.execute('SELECT pg_advisory_xact_lock(%s)', (int(chat_id),))
            cur.execute("DELETE FROM mx_telegram_rate_events WHERE occurred_at < NOW() - INTERVAL '60 seconds'")
            cur.execute("SELECT COUNT(*) FROM mx_telegram_rate_events WHERE chat_id=%s AND occurred_at >= NOW() - INTERVAL '60 seconds'", (chat_id,))
            if cur.fetchone()[0] >= limit: conn.rollback(); cur.close(); return False
            cur.execute('INSERT INTO mx_telegram_rate_events(chat_id) VALUES(%s)', (chat_id,))
            conn.commit(); cur.close(); return True
        finally: conn.close()

    def _query(self, sql, params=()):
        conn = self.get_db()
        if not conn: return []
        try:
            cur = conn.cursor(); cur.execute(sql, params); cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]; cur.close()
            return json.loads(json.dumps(rows, default=_json))
        except Exception as exc:
            conn.rollback(); return [{'unavailable': True, 'reason': str(exc)[:160]}]
        finally: conn.close()

    def run_tool(self, name, args, role):
        if not self._allowed(role): return {'error': 'Bu veri için data.read yetkisi gerekli.'}
        days = min(max(int((args or {}).get('days', 7)), 1), 90)
        if name == 'get_campaign_performance':
            return self._query("""SELECT marketplace_key AS channel,external_id AS campaign_id,MAX(name) AS name,
                SUM(spend) AS spend,SUM(clicks) AS clicks,SUM(orders) AS orders,SUM(revenue) AS revenue,
                CASE WHEN SUM(spend)>0 THEN SUM(revenue)/SUM(spend) ELSE 0 END AS roas
                FROM mx_normalized_metrics WHERE marketplace_key IN('meta','google','google_ads')
                AND captured_at>=NOW()-(%s||' days')::interval GROUP BY marketplace_key,external_id
                ORDER BY spend DESC LIMIT %s""", (days, 20 if role in ('admin','super_admin','editor') else 10))
        if name == 'get_ga4_summary':
            if self.ga4_token_getter and os.environ.get('GA4_PROPERTY_ID'):
                token = self.ga4_token_getter()
                if token:
                    response = requests.post('https://analyticsdata.googleapis.com/v1beta/properties/%s:runReport' % os.environ['GA4_PROPERTY_ID'],
                        headers={'Authorization':'Bearer '+token}, json={'dateRanges':[{'startDate':'%sdaysAgo' % days,'endDate':'today'}],
                        'dimensions':[{'name':'sessionSourceMedium'}],
                        'metrics':[{'name':'sessions'},{'name':'totalUsers'},{'name':'purchaseRevenue'},{'name':'conversions'}], 'limit':10}, timeout=30)
                    response.raise_for_status(); return response.json()
            return self._query("""SELECT captured_at,name,spend,revenue,orders,clicks,roas
                FROM mx_normalized_metrics WHERE marketplace_key='ga4' AND captured_at>=NOW()-(%s||' days')::interval
                ORDER BY captured_at DESC LIMIT %s""", (days, 20 if role in ('admin','super_admin') else 10))
        if name == 'get_trendyol_summary':
            return self._query("""SELECT captured_at,name,spend,revenue,orders,clicks,roas
                FROM mx_normalized_metrics WHERE marketplace_key='trendyol' AND captured_at>=NOW()-(%s||' days')::interval
                ORDER BY captured_at DESC LIMIT %s""", (days, 20 if role in ('admin','super_admin') else 10))
        if name == 'get_decision_queue':
            status = str((args or {}).get('status') or 'proposed')
            return self._query("""SELECT id,decision_date,marketplace_key,entity_name,decision_type,reason,priority,risk_level,status,
                current_budget,recommended_budget FROM mx_decisions WHERE status=%s ORDER BY decision_date DESC,id DESC LIMIT %s""", (status, 50 if role in ('admin','super_admin','editor') else 20))
        return {'error': 'Bilinmeyen araç'}

    def _anthropic(self, payload):
        response = self.http_post('https://api.anthropic.com/v1/messages', json=payload,
            headers={'x-api-key': self.api_key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}, timeout=45)
        response.raise_for_status(); return response.json()

    def _record_usage(self, chat_id, email, usage):
        tin, tout = int(usage.get('input_tokens') or 0), int(usage.get('output_tokens') or 0)
        cost = tin / 1_000_000 * float(os.environ.get('ANTHROPIC_INPUT_USD_PER_MTOK', '3')) + tout / 1_000_000 * float(os.environ.get('ANTHROPIC_OUTPUT_USD_PER_MTOK', '15'))
        conn = self.get_db()
        if not conn: self.memory_usage.append({'chat_id': chat_id, 'actor_email': email, 'tokens_in': tin, 'tokens_out': tout, 'cost_estimate_usd': cost}); return
        try:
            cur=conn.cursor(); cur.execute('INSERT INTO mx_ai_usage(chat_id,actor_email,tokens_in,tokens_out,cost_estimate_usd) VALUES(%s,%s,%s,%s,%s)', (chat_id,email,tin,tout,cost)); conn.commit(); cur.close()
        finally: conn.close()

    def answer(self, question, chat_id, email, role):
        if not self._allowed(role): return {'text': 'Bu veriyi analiz etmek için yetkiniz yok.', 'usage': {}}
        if not self.api_key: return {'text': 'Analiz motoru henüz yapılandırılmadı (ANTHROPIC_KEY eksik).', 'usage': {}}
        system = ('Madmext Ads salt-okunur analiz asistanısın. Yalnızca verilen araç sonuçlarına dayan. '
                  'Bütçe, rol veya yetki değiştirme; böyle bir istek gelirse admin paneline yönlendir. Türkçe ve kısa yanıt ver.')
        payload = {'model': self.model, 'max_tokens': 1200, 'system': system, 'tools': TOOLS,
                   'messages': [{'role':'user','content':question}]}
        first = self._anthropic(payload); usage = dict(first.get('usage') or {})
        tool_uses = [b for b in first.get('content', []) if b.get('type') == 'tool_use']
        if tool_uses:
            results = [{'type':'tool_result','tool_use_id':b['id'],
                        'content':json.dumps(self.run_tool(b['name'], b.get('input') or {}, role), ensure_ascii=False)} for b in tool_uses]
            payload['messages'] += [{'role':'assistant','content':first.get('content',[])}, {'role':'user','content':results}]
            final = self._anthropic(payload)
            usage['input_tokens'] = int(usage.get('input_tokens') or 0) + int((final.get('usage') or {}).get('input_tokens') or 0)
            usage['output_tokens'] = int(usage.get('output_tokens') or 0) + int((final.get('usage') or {}).get('output_tokens') or 0)
        else: final = first
        text = '\n'.join(b.get('text','') for b in final.get('content',[]) if b.get('type') == 'text').strip() or 'Analiz sonucu üretilemedi.'
        self._record_usage(chat_id, email, usage)
        return {'text': text, 'usage': usage}
