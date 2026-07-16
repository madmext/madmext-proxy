import clarity_flow


def test_full_export_plan_covers_every_published_dimension():
    plans = [tuple()] + [(dimension,) for dimension in clarity_flow.PUBLISHED_DIMENSIONS]
    assert len(plans) == clarity_flow.DAILY_REQUEST_LIMIT == 10
    assert {plan[0] for plan in plans if plan} == set(clarity_flow.PUBLISHED_DIMENSIONS)


def test_split_row_preserves_unknown_metrics():
    dimensions, metrics = clarity_flow._split_row(
        {"Device": "Mobile", "totalSessionCount": "12", "futureMetric": 7},
        ("Device",),
    )
    assert dimensions == {"Device": "Mobile"}
    assert metrics == {"totalSessionCount": "12", "futureMetric": 7}


def test_request_export_sends_bearer_and_dimensions(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [{"metricName": "Traffic", "information": []}]

    def fake_get(url, params, headers, timeout):
        captured.update(url=url, params=params, headers=headers, timeout=timeout)
        return Response()

    monkeypatch.setenv("CLARITY_API_TOKEN", "secret-token")
    monkeypatch.setenv("CLARITY_API_BASE_URL", "https://example.test/export")
    monkeypatch.setattr(clarity_flow.requests, "get", fake_get)

    status, payload, response_hash = clarity_flow._request_export(3, ("Browser", "Device"))

    assert status == 200
    assert payload[0]["metricName"] == "Traffic"
    assert response_hash
    assert captured["params"] == {
        "numOfDays": "3",
        "dimension1": "Browser",
        "dimension2": "Device",
    }
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
