import telegram_flow
import runtime
from datetime import date

from telegram_ai_engine import TelegramAIEngine, _resolve_date_range, split_telegram_message


HEADERS = {'X-Telegram-Bot-Api-Secret-Token': 'test-telegram-secret'}


def update(text, chat_id=7001):
    return {'update_id': 99, 'message': {'chat': {'id': chat_id, 'username': 'phase2'}, 'text': text}}


def link(chat_id=7001, role='viewer'):
    telegram_flow._memory_links[str(chat_id)] = {'telegram_chat_id': chat_id,
        'linked_email': 'viewer@example.com', 'role_snapshot': role, 'is_active': True}


def test_message_split_never_exceeds_telegram_limit():
    chunks = split_telegram_message(('analiz ' * 1000).strip())
    assert len(chunks) > 1
    assert all(len(chunk) <= 4096 for chunk in chunks)


def test_linked_question_uses_analysis_engine_and_splits_reply(client, monkeypatch):
    link()
    runtime.telegram_engine.memory_rate.clear()
    monkeypatch.setattr(runtime.telegram_engine, 'answer', lambda *args: {
        'text': 'x' * 5000, 'usage': {'input_tokens': 10, 'output_tokens': 20}})
    response = client.post('/telegram/webhook', headers=HEADERS, json=update('ROAS özeti nedir?'))
    assert response.status_code == 200
    assert len(response.get_json()['chunks']) == 2


def test_rate_limit_blocks_seventh_message(client, monkeypatch):
    link(7002)
    runtime.telegram_engine.memory_rate.clear()
    monkeypatch.setattr(runtime.telegram_engine, 'answer', lambda *args: {'text':'ok','usage':{}})
    responses = [client.post('/telegram/webhook', headers=HEADERS, json=update('rapor', 7002)) for _ in range(7)]
    assert [r.status_code for r in responses[:6]] == [200] * 6
    assert responses[6].status_code == 429
    assert responses[6].get_json()['rate_limited'] is True


def test_unknown_role_cannot_use_data_tools(client):
    result = runtime.telegram_engine.run_tool('get_decision_queue', {}, 'guest')
    assert 'yetki' in result['error'].lower()


def test_budget_request_stays_blocked_before_analysis(client, monkeypatch):
    link(7003, 'admin')
    monkeypatch.setattr(runtime.telegram_engine, 'answer', lambda *args: (_ for _ in ()).throw(AssertionError('AI çalışmamalı')))
    response = client.post('/telegram/webhook', headers=HEADERS, json=update('Bütçeyi 500 TL yap', 7003))
    assert response.status_code == 200
    assert 'admin panelinden' in response.get_json()['reply']


def test_claude_tool_use_records_usage_without_real_api(monkeypatch):
    class Response:
        def __init__(self, body): self.body = body
        def raise_for_status(self): pass
        def json(self): return self.body
    replies = iter([
        {'content':[{'type':'tool_use','id':'t1','name':'get_decision_queue','input':{}}],
         'usage':{'input_tokens':100,'output_tokens':20}},
        {'content':[{'type':'text','text':'Kuyruk özeti hazır.'}],
         'usage':{'input_tokens':50,'output_tokens':30}},
    ])
    engine = TelegramAIEngine(runtime.app, lambda: None, http_post=lambda *a, **k: Response(next(replies)))
    engine.api_key = 'mock-key'
    monkeypatch.setattr(engine, 'run_tool', lambda *a: [{'decision':'keep'}])
    result = engine.answer('Karar kuyruğunu özetle', 1, 'viewer@example.com', 'viewer')
    assert result['text'] == 'Kuyruk özeti hazır.'
    assert engine.memory_usage[0]['tokens_in'] == 150
    assert engine.memory_usage[0]['tokens_out'] == 50


def test_resolve_today_and_yesterday_ranges():
    today = date(2026, 7, 11)
    assert _resolve_date_range({'period': 'today'}, today) == (today, today)
    yesterday = date(2026, 7, 10)
    assert _resolve_date_range({'period': 'yesterday'}, today) == (yesterday, yesterday)


def test_resolve_explicit_and_last_n_day_ranges():
    today = date(2026, 7, 11)
    assert _resolve_date_range({'date_from': '2026-07-01', 'date_to': '2026-07-05'}, today) == (date(2026, 7, 1), date(2026, 7, 5))
    assert _resolve_date_range({'days': 7}, today) == (date(2026, 7, 5), today)


def test_resolve_date_range_rejects_invalid_ranges():
    today = date(2026, 7, 11)
    for args in (
        {'date_from': '2026-07-01'},
        {'date_from': '2026-07-12', 'date_to': '2026-07-12'},
        {'date_from': '2026-07-05', 'date_to': '2026-07-01'},
    ):
        try:
            _resolve_date_range(args, today)
            assert False, args
        except ValueError:
            pass
