import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_every_page_module_file_exists():
    index = (ROOT / 'index.html').read_text(encoding='utf-8')
    pages = re.search(r'const PAGES = \{(.*?)\n\};', index, re.S).group(1)
    modules = set(re.findall(r"module:'([^']+)'", pages))
    missing = [name for name in modules if name != 'create' and not (ROOT / 'modules' / f'{name}.html').exists()]
    assert missing == []


def test_ai_agency_uses_advanced_module_and_nested_url():
    index = (ROOT / 'index.html').read_text(encoding='utf-8')
    assert "'ai-ajans':    {title:'AI Ajans Merkezi'" in index
    assert "module:'ai-ajans-gpt', iframe:true" in index
    assert "'ai-ajans':'/ai-ajans'" in index
    assert "@app.route('/ai-ajans/<section>')" in (ROOT / 'app.py').read_text(encoding='utf-8')


def test_ai_agency_storage_keys_are_preserved():
    advanced = (ROOT / 'modules' / 'ai-ajans-gpt.html').read_text(encoding='utf-8')
    legacy_ui = (ROOT / 'modules' / 'ai-ajans-ui.js').read_text(encoding='utf-8')
    assert "const K='mxAj_',OLD='mxAgencyTasks_'" in advanced
    assert "GROUP_KEY='mxAgencyWorkGroups'" in legacy_ui
    assert "AGENT_META_KEY='mxAgencyAgentMeta'" in legacy_ui
    assert "localStorage.getItem('mxAgencyManagers')" in legacy_ui


def test_ai_agency_dependencies_are_linked():
    advanced = (ROOT / 'modules' / 'ai-ajans-gpt.html').read_text(encoding='utf-8')
    assert '/modules/ai-ajans-mobile.css' in advanced
    assert '/modules/ai-ajans-meeting.js' in advanced
    assert '/modules/ai-ajans-ui.js' in advanced
