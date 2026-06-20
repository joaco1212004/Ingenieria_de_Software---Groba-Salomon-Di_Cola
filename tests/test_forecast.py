from datetime import date

from fastapi.testclient import TestClient

from api.main import api
from api.security import API_KEY

client = TestClient(api)
AUTH_HEADERS = {"X-API-Key": API_KEY}


def test_get_forecast_ok(mock_db):
    mock_conn = mock_db.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.mappings.return_value.all.return_value = [
        {"date": date(2026, 3, 1), "prod": 150.5},
        {"date": date(2026, 4, 1), "prod": 162.0},
    ]

    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "NQ.NQ.TE-1",
            "date_start": "2026-03-01",
            "date_end": "2026-04-30",
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["id_well"] == "NQ.NQ.TE-1"
    assert len(data["data"]) == 2
    assert data["data"][0]["date"] == "2026-03-01"
    assert data["data"][0]["prod"] == 150.5


def test_get_forecast_invalid_dates():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "NQ.NQ.TE-1",
            "date_start": "2026-04-02",
            "date_end": "2026-03-30",
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 400


def test_get_forecast_invalid_format():
    response = client.get(
        "/api/v1/forecast",
        params={
            "id_well": "NQ.NQ.TE-1",
            "date_start": "2026/03/30",
            "date_end": "2026-04-02",
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 422
