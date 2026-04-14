"""Instrumentacion Prometheus para la API.

Define los counters/histograms y un middleware ASGI que los actualiza por
request. El endpoint /metrics se registra en api.main.

Las metricas estan nombradas con el prefijo 'predictiva_' y cubren los KPIs
de la adenda tecnica de Fase 1:
  - Latencia de respuesta (KPI objetivo: < 5 segundos).
  - Tasa de errores de la API (KPI uptime objetivo: 99.5%).
  - Frecuencia de consultas por endpoint.
"""

import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_LATENCY = Histogram(
    "predictiva_request_latency_seconds",
    "Latencia de las respuestas HTTP de la API en segundos.",
    labelnames=("method", "endpoint"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

REQUESTS_TOTAL = Counter(
    "predictiva_requests_total",
    "Cantidad total de requests HTTP recibidas por la API.",
    labelnames=("method", "endpoint", "status_code"),
)

REQUEST_ERRORS_TOTAL = Counter(
    "predictiva_request_errors_total",
    "Cantidad total de respuestas HTTP con status >= 400.",
    labelnames=("method", "endpoint", "status_code"),
)


class PrometheusMiddleware:
    """Middleware ASGI que instrumenta cada request HTTP.

    Usamos el patron ASGI puro (en lugar de BaseHTTPMiddleware) para poder
    leer el status_code final sin romper el streaming del response.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        endpoint = _resolve_endpoint(scope)
        start = time.perf_counter()
        status_holder = {"code": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if endpoint == "/metrics":
                return
            elapsed = time.perf_counter() - start
            status_code = str(status_holder["code"])
            REQUEST_LATENCY.labels(method, endpoint).observe(elapsed)
            REQUESTS_TOTAL.labels(method, endpoint, status_code).inc()
            if status_holder["code"] >= 400:
                REQUEST_ERRORS_TOTAL.labels(method, endpoint, status_code).inc()


def _resolve_endpoint(scope: Scope) -> str:
    """Devuelve la ruta templated (ej. '/api/v1/forecast') para agrupar series.

    Si el router aun no resolvio el path, cae al raw path del scope. Esto
    evita una explosion de cardinalidad por query params.
    """
    route = scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return scope.get("path", "unknown")


async def metrics_endpoint(_: Request) -> Response:
    """Handler del endpoint GET /metrics en formato text/plain Prometheus."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
