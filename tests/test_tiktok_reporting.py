from flask import Flask

import tiktok_reporting


class FakeResponse:
    ok = True
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def _test_app():
    app = Flask(__name__)
    app.config.update(TESTING=True)
    tiktok_reporting.install(
        app,
        get_db=lambda: None,
        require_admin=lambda: None,
    )
    return app


def test_campaigns_endpoint_normalizes_mock_tiktok_report(monkeypatch):
    monkeypatch.setattr(
        tiktok_reporting,
        "_active_accounts",
        lambda get_db: [
            {
                "advertiser_id": "adv-123",
                "access_token": "decrypted-access-token",
            }
        ],
    )

    def fake_get(url, params, headers, timeout):
        assert headers["Access-Token"] == "decrypted-access-token"
        assert timeout == tiktok_reporting.HTTP_TIMEOUT_SECONDS
        if url.endswith("/campaign/get/"):
            return FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "list": [
                            {
                                "campaign_id": "camp-42",
                                "campaign_name": "Yaz Koleksiyonu",
                                "operation_status": "ENABLE",
                            }
                        ]
                    },
                }
            )
        assert url.endswith("/report/integrated/get/")
        assert params["data_level"] == "AUCTION_CAMPAIGN"
        assert params["report_type"] == "BASIC"
        return FakeResponse(
            {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "dimensions": {"campaign_id": "camp-42"},
                            "metrics": {
                                "spend": "100.00",
                                "impressions": "10000",
                                "clicks": "250",
                                "complete_payment": "5",
                                "total_complete_payment_value": "450.00",
                                "complete_payment_roas": "4.5",
                            },
                        }
                    ]
                },
            }
        )

    monkeypatch.setattr(tiktok_reporting.requests, "get", fake_get)

    with _test_app().test_client() as client:
        response = client.get(
            "/api/tiktok/campaigns"
            "?start_date=2026-07-01&end_date=2026-07-07"
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["connected"] is True
    assert payload["read_only"] is True
    assert payload["summary"] == {
        "spend": 100.0,
        "impressions": 10000,
        "clicks": 250,
        "purchases": 5,
        "revenue": 450.0,
        "roas": 4.5,
        "ctr": 2.5,
        "cpc": 0.4,
    }
    assert payload["campaigns"][0] == {
        "advertiser_id": "adv-123",
        "campaign_id": "camp-42",
        "campaign_name": "Yaz Koleksiyonu",
        "status": "ENABLE",
        "spend": 100.0,
        "impressions": 10000,
        "clicks": 250,
        "purchases": 5,
        "revenue": 450.0,
        "roas": 4.5,
        "ctr": 2.5,
        "cpc": 0.4,
    }


def test_campaigns_endpoint_returns_connect_action_when_not_connected(monkeypatch):
    def disconnected(get_db):
        raise tiktok_reporting.TikTokNotConnectedError(
            "TikTok Ads hesabı bağlı değil"
        )

    monkeypatch.setattr(tiktok_reporting, "_active_accounts", disconnected)

    with _test_app().test_client() as client:
        response = client.get("/api/tiktok/campaigns")

    assert response.status_code == 409
    assert response.get_json() == {
        "ok": False,
        "connected": False,
        "read_only": True,
        "error": "TikTok Ads hesabı bağlı değil",
        "connect_url": "/api/integrations/tiktok/connect",
    }
