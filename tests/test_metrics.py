from fastapi.testclient import TestClient

from api.main import api
from api.security import API_KEY

client = TestClient(api)

API_KEY_HEADER = {"X-API-Key": API_KEY}


def _metrics_text() -> str:
    response = client.get("/metrics")
    assert response.status_code == 200
    return response.text


def _counter_value(text: str, metric: str, endpoint: str) -> float:
    total = 0.0
    for line in text.splitlines():
        if line.startswith("#") or not line.startswith(metric):
            continue
        if f'endpoint="{endpoint}"' not in line:
            continue
        total += float(line.rsplit(" ", 1)[-1])
    return total


def test_metrics_endpoint_responds_200():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_metrics_payload_contains_expected_metrics():
    text = _metrics_text()
    assert "predictiva_request_latency_seconds" in text
    assert "predictiva_requests_total" in text


def test_forecast_call_increments_counter():
    before = _counter_value(
        _metrics_text(), "predictiva_requests_total", "/api/v1/forecast"
    )

    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "WELL-001",
            "date_start": "2026-03-30",
            "date_end": "2026-04-02",
        },
        headers=API_KEY_HEADER,
    )
    assert response.status_code == 200

    after = _counter_value(
        _metrics_text(), "predictiva_requests_total", "/api/v1/forecast"
    )
    assert after > before


def test_wells_call_increments_counter():
    before = _counter_value(
        _metrics_text(), "predictiva_requests_total", "/api/v1/wells"
    )

    response = client.get(
        "/api/v1/wells",
        params={"date_query": "2026-03-30"},
        headers=API_KEY_HEADER,
    )
    assert response.status_code == 200

    after = _counter_value(
        _metrics_text(), "predictiva_requests_total", "/api/v1/wells"
    )
    assert after > before
