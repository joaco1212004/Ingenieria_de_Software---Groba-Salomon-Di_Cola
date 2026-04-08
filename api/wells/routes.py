from fastapi import APIRouter, Depends, Query
from datetime import date
from api.security import verify_api_key

router = APIRouter()

@router.get("/wells")
def get_wells(
    date_query: date = Query(..., description="Fecha para la consulta"),
    _: str = Depends(verify_api_key)
):
    return [
        {"id_well": "WELL-001"},
        {"id_well": "WELL-002"},
        {"id_well": "WELL-003"}
    ]
