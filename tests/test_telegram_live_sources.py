import app as app_module
import runtime
from telegram_ai_engine import TelegramAIEngine


def test_campaign_tool_reads_meta_sync_time_and_shared_google_service(monkeypatch):
    seen = {}
    engine = TelegramAIEngine(runtime.app, lambda: None,
        gads_campaign_fetcher=lambda payload: seen.setdefault('payload', payload) or {'rows': []})
    def query(sql, params=()):
        if 'MAX(last_synced_at) AS last_synced_at FROM meta_ad_insights' in sql:
            return [{'last_synced_at':'2026-07-11T12:30:00'}]
        return [{'campaign_id':'m1','name':'Meta Kampanya','spend':100,'revenue':400,
                 'clicks':20,'orders':4,'roas':4,'last_synced_at':'2026-07-11T12:00:00'}]
    monkeypatch.setattr(engine, '_query', query)
    result = engine.run_tool('get_campaign_performance', {'days': 7}, 'viewer')
    assert result['meta_ads']['source_table'] == 'meta_ad_insights'
    assert result['meta_ads']['last_synced_at'] == '2026-07-11T12:30:00'
    assert 'en son' in result['meta_ads']['freshness_note'].lower()
    assert result['google_ads']['source_function'] == 'gads_campaign_rows'
    assert seen['payload']['date_from'] <= seen['payload']['date_to']


def test_trendyol_tool_reads_all_real_tables_and_normalizes_numbers(monkeypatch):
    engine = TelegramAIEngine(runtime.app, lambda: None)
    monkeypatch.setattr(engine, '_query', lambda sql, params=(): [
        {'source':'ty_urun','name':'A','status':'Aktif','spend':'1.234,50','revenue':'4.000,00','orders':'10','clicks':'100','impressions':'1000','roas':'3,24','created_at':'2026-07-11'},
        {'source':'ty_meta','name':'B','status':'Aktif','spend':'100','revenue':'300','orders':'2','clicks':'20','impressions':'200','roas':'3','created_at':'2026-07-11'},
    ])
    result = engine.run_tool('get_trendyol_summary', {'days': 30}, 'viewer')
    assert result['source_tables'] == ['ty_urun','ty_urun_detay','ty_magaza','ty_influencer','ty_meta']
    assert result['source_counts'] == {'ty_urun':1,'ty_meta':1}
    assert result['totals']['spend'] == 1334.5
    assert result['totals']['revenue'] == 4300.0


def test_shared_google_service_keeps_date_and_campaign_validation():
    for payload in (
        {'date_from': "2026-01-01' OR 1=1", 'date_to':'2026-01-31'},
        {'campaign_id':'1 OR 1=1', 'date_range':'LAST_7_DAYS'},
    ):
        try:
            app_module.gads_campaign_rows(payload)
            assert False, 'ValueError bekleniyordu'
        except ValueError:
            pass


def test_shared_google_service_builds_read_only_validated_gaql(monkeypatch):
    captured = {}
    class Response:
        text = '{"results":[]}'
        status_code = 200
        def json(self): return {'results':[]}
    monkeypatch.setattr(app_module, 'gads_get_token', lambda: 'mock-token')
    monkeypatch.setattr(app_module, 'GADS_CUSTOMER_ID', '123-456')
    monkeypatch.setattr(app_module, 'GADS_DEVELOPER_TOKEN', 'dev-token')
    def post(url, **kwargs): captured.update(url=url, **kwargs); return Response()
    result = app_module.gads_campaign_rows({
        'campaign_id':'123','date_from':'2026-07-01','date_to':'2026-07-11'}, http_post=post)
    query = captured['json']['query']
    assert "segments.date BETWEEN '2026-07-01' AND '2026-07-11'" in query
    assert "campaign.id = '123'" in query
    assert result == {'rows': [], 'configured': True}
