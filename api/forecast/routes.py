"""GET /api/v1/forecast: prediccion de produccion mensual por pozo (ADR-0023).

Reemplaza el mock de Fase 1 (que devolvia historia del warehouse) por
inferencia online real: carga el modelo en stage Production del registry
(api/ml_model.py), trae la serie historica del pozo desde el feature mart
(api/feature_client.py) y predice los meses futuros pedidos.

Contrato (compatible con el original): query params `id_well` (sigla),
`date_start`, `date_end`; respuesta `{id_well, model_version, unit, data:
[{date, prod}]}`. `prod` es produccion mensual estimada = tasa diaria predicha
x dias del mes (aproxima tef = mes completo; el modelo predice tasa diaria,
que es la senal robusta al downtime).

Errores explicitos (sin fallback a historia, decision del ADR-0023):
- 400 rango invalido o que pisa la historia (esto es un forecast, la historia
  se consulta en el warehouse/Metabase).
- 404 pozo inexistente.
- 503 modelo no disponible / historia insuficiente / Arps no ajusta.
"""

from datetime import date

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Engine

from api.db import get_engine
from api.feature_client import (
    InsufficientHistory,
    WellNotFound,
    get_well_series,
)
from api.metrics import FORECASTS_TOTAL
from api.ml_model import ModelUnavailable, get_model
from api.security import verify_api_key

router = APIRouter()


@router.get("/forecast")
def get_forecast(
    id_well: str = Query(..., description="Sigla del pozo (gold.dim_pozo)"),
    date_start: date = Query(..., description="Fecha inicial del pronostico"),
    date_end: date = Query(..., description="Fecha final del pronostico"),
    _: str = Depends(verify_api_key),
    engine: Engine = Depends(get_engine),
):
    if date_end < date_start:
        raise HTTPException(
            status_code=400, detail="date_end no puede ser menor a date_start"
        )

    try:
        modelo = get_model()
        serie = get_well_series(engine, id_well)
    except WellNotFound as exc:
        FORECASTS_TOTAL.labels(status="error_data").inc()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InsufficientHistory as exc:
        FORECASTS_TOTAL.labels(status="error_data").inc()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ModelUnavailable as exc:
        FORECASTS_TOTAL.labels(status="error_model").inc()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Meses pedidos -> indices globales de la serie (meses desde primer_mes).
    meses = pd.period_range(
        pd.Period(date_start, freq="M"), pd.Period(date_end, freq="M"), freq="M"
    )
    indices = np.array([(m - serie.primer_mes).n for m in meses])

    # Solo se pronostican meses POSTERIORES al ultimo dato observado.
    if indices[0] < len(serie.q):
        FORECASTS_TOTAL.labels(status="error_data").inc()
        raise HTTPException(
            status_code=400,
            detail=(
                f"el rango pedido pisa la historia del pozo (ultimo dato: "
                f"{serie.ultimo_mes}); /forecast solo pronostica meses futuros"
            ),
        )

    # k_tr = toda la historia como train: el predictor re-ajusta Arps al pozo
    # y la LSTM corrige el residual (contrato de pipeline/ml/m3.py).
    tasas = modelo.predictor(
        serie.pid, serie.q, len(serie.q), None, indices.astype(float)
    )
    if tasas is None:
        FORECASTS_TOTAL.labels(status="error_model").inc()
        raise HTTPException(
            status_code=503,
            detail=(
                f"la curva de declino no ajusta para el pozo '{id_well}' "
                "(historia post-pico insuficiente)"
            ),
        )

    data = [
        {
            "date": m.to_timestamp(how="end").date().isoformat(),
            "prod": round(float(tasa) * m.days_in_month, 3),
        }
        for m, tasa in zip(meses, tasas)
    ]
    FORECASTS_TOTAL.labels(status="success").inc()
    return {
        "id_well": id_well,
        "model_version": modelo.version,
        "unit": "m3/mes estimados (tasa diaria predicha x dias del mes)",
        "data": data,
    }
