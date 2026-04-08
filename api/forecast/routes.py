from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import date, timedelta
from api.security import verify_api_key

router = APIRouter()


@router.get("/forecast")
def get_forecast(
    id_well: str = Query(..., description="Identificador del pozo"),
    date_start: date = Query(..., description="Fecha inicial"),
    date_end: date = Query(..., description="Fecha final"),
    _: str = Depends(verify_api_key),
):
    if date_end < date_start:
        raise HTTPException(
            status_code=400, detail="date_end no puede ser menor a date_start"
        )

    forecast = []
    current = date_start
    vol_produced = 100.0

    while current <= date_end:
        forecast.append({"date": current.isoformat(), "prod": round(vol_produced, 2)})
        current += timedelta(days=1)
        vol_produced += 2.5

    return {"id_well": id_well, "data": forecast}
