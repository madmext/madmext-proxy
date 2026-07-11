from flask import Flask

import telegram_flow


def _isolated_app(monkeypatch):
    monkeypatch.setenv('TELEGRAM_WEBHOOK_SECRET', 'isolated-secret')
    monkeypatch.delenv('TELEGRAM_TEST_MEMORY_FALLBACK', raising=False)
    app = Flask(__name__)
    app.secret_key = 'test'
    audits = []
    app.extensions['mx_audit'] = lambda action, **details: audits.append((action, details))
    telegram_flow.install(app, get_db=lambda: None, get_users=lambda: [],
        hash_pw=lambda value: value, verify_pw=lambda stored, value: False,
        save_users=lambda users: None)
    app.config['TESTING'] = True
    return app, audits


def test_production_invite_creation_requires_database(monkeypatch):
    app, audits = _isolated_app(monkeypatch)
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['user_email'] = 'admin@example.com'
            session['user_role'] = 'admin'
        response = client.post('/admin/telegram/invites', json={'max_uses':1,'expires_in_hours':24})
    assert response.status_code == 503
    assert any(action == 'telegram.database_unavailable' for action, _ in audits)


def test_production_webhook_requires_database(monkeypatch):
    app, audits = _isolated_app(monkeypatch)
    with app.test_client() as client:
        response = client.post('/telegram/webhook',
            headers={'X-Telegram-Bot-Api-Secret-Token':'isolated-secret'},
            json={'update_id':1,'message':{'chat':{'id':44},'text':'/start secret-token'}})
    assert response.status_code == 503
    assert any(action == 'telegram.database_unavailable' for action, _ in audits)


def test_audit_uses_fingerprint_not_raw_token(client, monkeypatch):
    token = 'never-log-this-full-token'
    calls = []
    monkeypatch.setitem(client.application.extensions, 'mx_audit',
                        lambda action, **details: calls.append((action, details)))
    client.post('/telegram/webhook',
        headers={'X-Telegram-Bot-Api-Secret-Token':'test-telegram-secret'},
        json={'update_id':2,'message':{'chat':{'id':991},'text':'/start '+token}})
    serialized = repr(calls)
    assert token not in serialized
    received = next(details for action, details in calls if action == 'telegram.message_received')
    assert len(received['metadata']['token_fingerprint']) == 16
