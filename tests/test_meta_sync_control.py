from pathlib import Path

import meta_sync_flow


def test_meta_module_exposes_account_id_for_sync_control():
    html = Path('modules/meta-ads.html').read_text(encoding='utf-8')
    assert 'window.AID = AID;' in html


def test_sync_control_is_visible_in_top_row_and_uses_window_account():
    html = Path('modules/meta-ads.html').read_text(encoding='utf-8')
    injected = meta_sync_flow._inject_meta_module(html)
    row1_end = injected.index('<!-- Satır 2: Filtreler -->')
    button_pos = injected.index('id="mxMetaSyncBtn"')
    assert button_pos < row1_end
    assert "adAccountId:String(window.AID||'').trim()" in injected
    assert 'insightsUpdated' in injected
    assert 'Güncelleme başarısız: ' in injected


def test_sync_control_is_not_duplicated():
    html = Path('modules/meta-ads.html').read_text(encoding='utf-8')
    once = meta_sync_flow._inject_meta_module(html)
    twice = meta_sync_flow._inject_meta_module(once)
    assert twice.count('id="mxMetaSyncBtn"') == 1


def test_shared_bootstrap_exposes_meta_account_before_dynamic_modules_load():
    shared = Path('modules/shared.js').read_text(encoding='utf-8')
    aid_declaration = shared.index("const AID='act_1346348685568168';")
    aid_export = shared.index('window.AID = AID;')
    assert aid_declaration < aid_export


def test_meta_insights_attribution_windows_are_sent_as_graph_json(monkeypatch):
    calls = []

    def fake_all_pages(path, params=None, max_pages=20):
        calls.append((path, dict(params or {})))
        return []

    monkeypatch.setattr(meta_sync_flow, '_all_pages', fake_all_pages)
    meta_sync_flow._meta_fetch_all('act_123', date_preset='last_7d')

    insights_params = next(params for path, params in calls if path.endswith('/insights'))
    assert insights_params['action_attribution_windows'] == '["7d_click", "1d_view"]'
