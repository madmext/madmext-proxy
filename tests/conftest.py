import os
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('ADMIN_EMAIL', 'admin@example.com')
os.environ.setdefault('ADMIN_PASSWORD', 'admin-pass')
os.environ.setdefault('SESSION_COOKIE_SECURE', 'false')
os.environ.setdefault('SHADOW_MODE', 'false')
os.environ.setdefault('GLOBAL_KILL_SWITCH', 'false')
os.environ.setdefault('PROVIDER_WRITES_ENABLED', 'true')
os.environ.setdefault('GOOGLE_WRITES_ENABLED', 'true')
os.environ.setdefault('TELEGRAM_WEBHOOK_SECRET', 'test-telegram-secret')
os.environ.pop('DATABASE_URL', None)

import app as app_module
import runtime


@pytest.fixture()
def client(tmp_path):
    app_module.app.config.update(TESTING=True)
    app_module.LOG_FILE = str(tmp_path / 'madmext_logs.json')
    app_module._users_cache = [{
        'email': 'admin@example.com',
        'name': 'Admin',
        'role': 'admin',
        'password_hash': app_module.hash_pw('admin-pass'),
        'is_active': True,
        'is_allowed': True,
    }, {
        'email': 'viewer@example.com',
        'name': 'Viewer',
        'role': 'viewer',
        'password_hash': app_module.hash_pw('viewer-pass'),
        'is_active': True,
        'is_allowed': True,
    }]
    with runtime.app.test_client() as test_client:
        yield test_client
