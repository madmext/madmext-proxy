def test_login_accepts_correct_password(client):
    response = client.post('/auth/login', json={
        'email': 'admin@example.com',
        'password': 'admin-pass',
    })
    assert response.status_code == 200
    assert response.get_json()['ok'] is True


def test_login_rejects_wrong_password(client):
    response = client.post('/auth/login', json={
        'email': 'admin@example.com',
        'password': 'wrong-password',
    })
    assert response.status_code == 401


def test_google_budget_requires_login(client):
    response = client.post('/gads/budget', json={
        'budget_id': '123',
        'amount_tl': 100,
    })
    assert response.status_code == 401


def test_google_toggle_requires_login(client):
    response = client.post('/gads/toggle', json={
        'campaign_id': '123',
        'status': 'PAUSED',
    })
    assert response.status_code == 401


def test_xml_proxy_requires_login(client):
    response = client.get('/proxy-xml?url=https://example.com/feed.xml')
    assert response.status_code == 401


def test_admin_users_rejects_non_admin(client):
    with client.session_transaction() as session:
        session['user_email'] = 'viewer@example.com'
        session['user_role'] = 'viewer'
    response = client.get('/admin/users')
    assert response.status_code == 403


def _set_admin_session(client):
    with client.session_transaction() as session:
        session['user_email'] = 'admin@example.com'
        session['user_role'] = 'super_admin'


def test_google_campaigns_rejects_invalid_dates(client):
    _set_admin_session(client)
    response = client.post('/gads/campaigns', json={
        'date_from': "2026-01-01' OR 1=1",
        'date_to': '2026-01-31',
    })
    assert response.status_code == 400


def test_google_adgroups_rejects_invalid_campaign_id(client):
    _set_admin_session(client)
    response = client.post('/gads/adgroups', json={
        'campaign_id': "123' OR 1=1",
        'date_range': 'LAST_7_DAYS',
    })
    assert response.status_code == 400


def test_google_budget_rejects_invalid_budget_id(client):
    _set_admin_session(client)
    response = client.post('/gads/budget', json={
        'budget_id': '12/../../34',
        'amount_tl': 100,
    })
    assert response.status_code == 400


def test_google_toggle_rejects_invalid_campaign_id(client):
    _set_admin_session(client)
    response = client.post('/gads/toggle', json={
        'campaign_id': '1 OR 1=1',
        'status': 'PAUSED',
    })
    assert response.status_code == 400
