from fastapi.testclient import TestClient
from api.main import api
from api.security import API_KEY

client = TestClient(api)


def test_get_wells_ok():
    response = client.get(
        "/api/v1/wells",
        params={"date_query": "2026-03-30"},
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id_well" in data[0]


def test_get_wells_no_api_key():
    response = client.get("/api/v1/wells", params={"date_query": "2026-03-30"})

    assert response.status_code == 403
