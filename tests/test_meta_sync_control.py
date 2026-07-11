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
