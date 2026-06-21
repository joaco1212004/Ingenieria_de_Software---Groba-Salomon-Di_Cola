from fastapi.testclient import TestClient

from api.main import api
from api.security import API_KEY

client = TestClient(api)
AUTH_HEADERS = {"X-API-Key": API_KEY}


def test_get_wells_ok(mock_db):
    mock_conn = mock_db.connect.return_value.__enter__.return_value
    mock_conn.execute.return_value.mappings.return_value.all.return_value = [
        {"id_well": "NQ.NQ.TE-1"},
        {"id_well": "NQ.NQ.TE-2"},
    ]

    response = client.get(
        "/api/v1/wells",
        params={"date_query": "2026-03-30"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id_well" in data[0]


def test_get_wells_no_api_key():
    response = client.get("/api/v1/wells", params={"date_query": "2026-03-30"})

    assert response.status_code == 403
