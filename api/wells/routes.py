from fastapi import APIRouter, Depends, Query
from api.security import verify_api_key

router = APIRouter()

@router.get("/wells")
def get_wells(
    date_query: str = Query(..., description="Fecha para la consulta"),
    _: str = Depends(verify_api_key)
):
    return {
        "date_query" : date_query,
        "wells" : [
            {"id_well" : "WELL-001", "name" : "Pozo Norte"},
            {"id_well" : "WELL-002", "name" : "Pozo Sur"},
            {"id_well" : "WELL-003", "name" : "Pozo Central"}
        ]
    }