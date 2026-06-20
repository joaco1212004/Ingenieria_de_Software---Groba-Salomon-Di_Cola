from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.engine import Engine

from api.db import get_engine
from api.security import verify_api_key

router = APIRouter()

_WELLS_QUERY = text("""
    SELECT DISTINCT dp.sigla AS id_well
    FROM gold.dim_pozo dp
    JOIN gold.fct_produccion_pozo_mes f ON dp.sk_pozo = f.sk_pozo
    JOIN gold.dim_tiempo dt ON f.sk_tiempo = dt.sk_tiempo
    WHERE dt.fecha_periodo <= :date_query
      AND dp.sigla != 'DESCONOCIDO'
    ORDER BY dp.sigla
""")


@router.get("/wells")
def get_wells(
    date_query: date = Query(..., description="Fecha para la consulta"),
    _: str = Depends(verify_api_key),
    engine: Engine = Depends(get_engine),
):
    with engine.connect() as conn:
        rows = conn.execute(_WELLS_QUERY, {"date_query": date_query}).mappings().all()
    return [{"id_well": row["id_well"]} for row in rows]
