from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import datetime, timedelta
from api.security import verify_api_key

router = APIRouter()

@router.get("/forecast")
def get_forecast (
    id_well : str = Query(..., description = "Identificador del pozo"),
    date_start : str = Query (..., description = "Fecha inicial"),
    date_end : str = Query (..., description = "Fecha final"),
    _ : str = Depends(verify_api_key)
):
    try : 
        start = datetime.strptime(date_start, "%Y-%m-%d").date()
        end = datetime.strptime(date_end, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code = 400, detail = "Formato de fecha invalido. Use YYYY-mm-dd")
    
    if end < start:
        raise HTTPException(status_code = 400, detail = "date_end no puede ser menor a date_start")
    
    forecast = []
    current = start
    vol_produced = 100.0  

    while current <= end:
        forecast.append({
            "date" : current.isoformat(),
            "vol_produced" : round(vol_produced, 2)
        })
        
        current += timedelta(days = 1)
        vol_produced += 2.5
    
    return {
        "id_well" : id_well,
        "forecast" : forecast
    }