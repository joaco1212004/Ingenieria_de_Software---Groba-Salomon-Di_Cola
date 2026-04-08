from fastapi.testclient import TestClient
from api.main import api

client = TestClient(api)


def test_get_forecast_ok():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "WELL-001",
            "date_start": "2026-03-30",
            "date_end": "2026-04-02",
        },
        headers={"X-API-Key": "abcdef12345"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data


def test_get_forecast_invalid_dates():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "WELL-001",
            "date_start": "2026-04-02",
            "date_end": "2026-03-30",
        },
        headers={"X-API-Key": "abcdef12345"},
    )

    assert response.status_code == 400


def test_get_forecast_invalid_format():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "WELL-001",
            "date_start": "2026/03/30",
            "date_end": "2026-04-02",
        },
        headers={"X-API-Key": "abcdef12345"},
    )

    assert response.status_code == 422
