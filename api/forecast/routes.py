from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.engine import Engine

from api.db import get_engine
from api.security import verify_api_key

router = APIRouter()

_FORECAST_QUERY = text(
    """
    SELECT dt.fecha_periodo AS date, f.prod_pet AS prod
    FROM gold.fct_produccion_pozo_mes f
    JOIN gold.dim_pozo dp ON f.sk_pozo = dp.sk_pozo
    JOIN gold.dim_tiempo dt ON f.sk_tiempo = dt.sk_tiempo
    WHERE dp.sigla = :id_well
      AND dt.fecha_periodo BETWEEN :date_start AND :date_end
    ORDER BY dt.fecha_periodo
"""
)


@router.get("/forecast")
def get_forecast(
    id_well: str = Query(..., description="Identificador del pozo"),
    date_start: date = Query(..., description="Fecha inicial"),
    date_end: date = Query(..., description="Fecha final"),
    _: str = Depends(verify_api_key),
    engine: Engine = Depends(get_engine),
):
    if date_end < date_start:
        raise HTTPException(
            status_code=400, detail="date_end no puede ser menor a date_start"
        )

    with engine.connect() as conn:
        rows = (
            conn.execute(
                _FORECAST_QUERY,
                {"id_well": id_well, "date_start": date_start, "date_end": date_end},
            )
            .mappings()
            .all()
        )

    data = [{"date": row["date"].isoformat(), "prod": row["prod"]} for row in rows]
    return {"id_well": id_well, "data": data}
