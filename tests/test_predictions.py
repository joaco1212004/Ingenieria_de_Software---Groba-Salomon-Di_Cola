"""Tests del serving de predicciones (ADR-0023).

Reemplaza a test_forecast.py (que testeaba el mock SQL de Fase 1). Se mockean
las dos dependencias externas del endpoint — el modelo del registry
(api.ml_model.get_model) y el feature mart (api.feature_client.get_well_series)
— para ejercitar el contrato HTTP completo sin MLflow ni Postgres.
"""

import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.feature_client import InsufficientHistory, WellNotFound, WellSeries
from api.main import api
from api.ml_model import LoadedModel, ModelUnavailable
from api.security import API_KEY

client = TestClient(api)
AUTH_HEADERS = {"X-API-Key": API_KEY}

SIGLA = "NQ.NQ.TE-1"
TASA = 2.0  # tasa diaria constante que devuelve el predictor mockeado


def _serie_ok() -> WellSeries:
    """24 meses de historia terminando en 2026-05 (predicciones desde 2026-06)."""
    q = np.linspace(10.0, 3.0, 24)
    return WellSeries(pid=1234, q=q, primer_mes=pd.Period("2024-06", freq="M"))


def _modelo_ok(tasas=TASA) -> LoadedModel:
    def predictor(pid, q, k_tr, k_va, t):
        if tasas is None:
            return None
        return np.full(len(t), tasas)

    return LoadedModel(
        predictor=predictor, version=3, horizonte=60, loaded_at=time.monotonic()
    )


@pytest.fixture
def serving_ok(monkeypatch):
    monkeypatch.setattr("api.forecast.routes.get_model", lambda: _modelo_ok())
    monkeypatch.setattr(
        "api.forecast.routes.get_well_series", lambda engine, sigla: _serie_ok()
    )


def _get(params):
    defaults = {
        "id_well": SIGLA,
        "date_start": "2026-06-01",
        "date_end": "2026-08-31",
    }
    return client.get(
        "/api/v1/forecast", params={**defaults, **params}, headers=AUTH_HEADERS
    )


def test_forecast_ok_devuelve_predicciones(serving_ok):
    response = _get({})

    assert response.status_code == 200
    body = response.json()
    assert body["id_well"] == SIGLA
    assert body["model_version"] == 3
    assert "unit" in body
    assert len(body["data"]) == 3  # jun, jul, ago
    # prod = tasa diaria x dias del mes; fechas = fin de mes ISO
    assert body["data"][0] == {"date": "2026-06-30", "prod": TASA * 30}
    assert body["data"][1] == {"date": "2026-07-31", "prod": TASA * 31}


def test_forecast_sin_modelo_en_production(monkeypatch):
    def sin_modelo():
        raise ModelUnavailable("no hay version en Production")

    monkeypatch.setattr("api.forecast.routes.get_model", sin_modelo)
    monkeypatch.setattr(
        "api.forecast.routes.get_well_series", lambda engine, sigla: _serie_ok()
    )

    response = _get({})
    assert response.status_code == 503
    assert "Production" in response.json()["detail"]


def test_forecast_historia_insuficiente(monkeypatch):
    monkeypatch.setattr("api.forecast.routes.get_model", lambda: _modelo_ok())

    def sin_historia(engine, sigla):
        raise InsufficientHistory("historia insuficiente")

    monkeypatch.setattr("api.forecast.routes.get_well_series", sin_historia)

    response = _get({})
    assert response.status_code == 503


def test_forecast_pozo_inexistente(monkeypatch):
    monkeypatch.setattr("api.forecast.routes.get_model", lambda: _modelo_ok())

    def no_existe(engine, sigla):
        raise WellNotFound(f"pozo '{sigla}' inexistente")

    monkeypatch.setattr("api.forecast.routes.get_well_series", no_existe)

    response = _get({})
    assert response.status_code == 404


def test_forecast_rango_pisa_historia(serving_ok):
    # la serie termina en 2026-05: pedir desde 2026-01 pisa la historia
    response = _get({"date_start": "2026-01-01", "date_end": "2026-08-31"})
    assert response.status_code == 400
    assert "historia" in response.json()["detail"]


def test_forecast_arps_no_ajusta(monkeypatch):
    monkeypatch.setattr("api.forecast.routes.get_model", lambda: _modelo_ok(tasas=None))
    monkeypatch.setattr(
        "api.forecast.routes.get_well_series", lambda engine, sigla: _serie_ok()
    )

    response = _get({})
    assert response.status_code == 503
    assert "declino" in response.json()["detail"]


def test_forecast_fechas_invertidas():
    response = _get({"date_start": "2026-08-01", "date_end": "2026-06-30"})
    assert response.status_code == 400


def test_forecast_formato_invalido():
    response = _get({"date_start": "2026/06/01"})
    assert response.status_code == 422
