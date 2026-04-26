"""Modulo principal de la aplicacion FastAPI."""

from fastapi import FastAPI, HTTPException

from api.forecast.routes import router as forecast_router
from api.metrics import PrometheusMiddleware, metrics_endpoint
from api.wells.routes import router as wells_router

api = FastAPI(
    title="Mock Forecast API",
    version="1.0.0",
    description="Mock del servicio API Rest para consultas de pronostico",
)

api.add_middleware(PrometheusMiddleware)

api.include_router(forecast_router, prefix="/api/v1", tags=["forecast"])
api.include_router(wells_router, prefix="/api/v1", tags=["wells"])

api.add_api_route(
    "/metrics",
    metrics_endpoint,
    methods=["GET"],
    summary="Prometheus Metrics",
    description="Devuelve métricas de Prometheus en formato text/plain",
    responses={200: {"description": "Métricas en formato Prometheus"}},
    tags=["monitoring"],
)


@api.get(
    "/api/v1/_debug/error",
    tags=["debug"],
    summary="Disparar HTTP 500 para validar dashboard y alertas",
    responses={500: {"description": "Error simulado"}},
)
def trigger_error():
    """Endpoint de debug que dispara un HTTP 500 deliberadamente.

    Sirve para validar que el panel "Error Rate" del dashboard
    detecta errores del servidor y que la regla de alerta
    TasaErrorAlta se dispara correctamente. No tiene utilidad
    funcional en producción.
    """
    raise HTTPException(status_code=500, detail="Error simulado")
