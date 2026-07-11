from datetime import datetime, timedelta, timezone

import telegram_flow


SECRET_HEADER = {'X-Telegram-Bot-Api-Secret-Token': 'test-telegram-secret'}


def _telegram_update(text, chat_id=12345, username='tester'):
    return {
        'update_id': 1,
        'message': {
            'message_id': 10,
            'chat': {'id': chat_id, 'username': username},
            'from': {'id': chat_id, 'username': username},
            'text': text,
        },
    }


def _admin_session(client):
    with client.session_transaction() as session:
        session['user_email'] = 'admin@example.com'
        session['user_role'] = 'admin'


def test_telegram_webhook_rejects_invalid_secret_before_processing(client):
    response = client.post('/telegram/webhook', json=_telegram_update('/start abc'))
    assert response.status_code == 403


def test_admin_can_create_viewer_invite(client):
    _admin_session(client)
    response = client.post('/admin/telegram/invites', json={'max_uses': 2, 'expires_in_hours': 24})
    assert response.status_code == 201
    body = response.get_json()
    assert body['invite']['role'] == 'viewer'
    assert body['invite']['max_uses'] == 2
    assert body['invite']['token']


def test_valid_invite_can_link_existing_account(client):
    _admin_session(client)
    invite = client.post('/admin/telegram/invites', json={}).get_json()['invite']['token']

    response = client.post('/telegram/webhook', headers=SECRET_HEADER,
                           json=_telegram_update('/start ' + invite))
    assert response.status_code == 200
    assert '/login' in response.get_json()['reply']

    response = client.post('/telegram/webhook', headers=SECRET_HEADER,
                           json=_telegram_update('/login %s viewer@example.com viewer-pass' % invite))
    assert response.status_code == 200
    assert response.get_json()['linked'] is True
    assert response.get_json()['role'] == 'viewer'


def test_expired_invite_is_rejected(client):
    telegram_flow._memory_invites['expired-token'] = {
        'invite_token': 'expired-token', 'created_by': 'admin@example.com', 'role': 'viewer',
        'max_uses': 1, 'used_count': 0,
        'expires_at': datetime.now(timezone.utc) - timedelta(minutes=1), 'is_active': True,
    }
    response = client.post('/telegram/webhook', headers=SECRET_HEADER,
                           json=_telegram_update('/start expired-token', chat_id=222))
    assert response.status_code == 200
    assert 'süresi' in response.get_json()['reply'].lower()


def test_unlinked_user_cannot_query_data(client):
    response = client.post('/telegram/webhook', headers=SECRET_HEADER,
                           json=_telegram_update('Dünkü ROAS nedir?', chat_id=987654))
    assert response.status_code == 200
    body = response.get_json()
    assert body['linked'] is False
    assert 'bağla' in body['reply'].lower()


def test_invite_cannot_grant_admin_role(client):
    _admin_session(client)
    response = client.post('/admin/telegram/invites', json={'role': 'admin'})
    assert response.status_code == 400


def test_telegram_credentials_are_never_copied_to_generic_audit(client, monkeypatch):
    calls = []
    monkeypatch.setitem(client.application.extensions, 'mx_audit',
                        lambda action, **details: calls.append((action, details)))
    client.post('/telegram/webhook', headers=SECRET_HEADER,
                json=_telegram_update('/login token viewer@example.com super-secret-password'))
    serialized = repr(calls)
    assert 'super-secret-password' not in serialized
