"""Modulo principal de la aplicacion FastAPI."""

from fastapi import FastAPI

from api.forecast.routes import router as forecast_router
from api.wells.routes import router as wells_router

api = FastAPI(
    title="Mock Forecast API",
    version="1.0.0",
    description="Mock del servicio API Rest para consultas de pronostico",
)

api.include_router(forecast_router, prefix="/api/v1", tags=["forecast"])
api.include_router(wells_router, prefix="/api/v1", tags=["wells"])
