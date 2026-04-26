"""Instrumentación Prometheus para la API.

RESPONSABILIDADES (basado en tutorial.md sección 0):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Esta capa (api/metrics.py) **PRODUCE** métricas observando eventos de negocio
(request HTTP, errores, latencias). El middleware es **puro ASGI** para no
romper streaming de responses.

No se encarga de:
  ❌ Almacenar series de tiempo (responsabilidad de Prometheus TSDB)
  ❌ Agregar, promediar, calcular percentiles (responsabilidad de PromQL)
  ❌ Disparar alertas (responsabilidad de Prometheus rules + Grafana)
  ❌ Enviar notificaciones (responsabilidad de contact points)

MÉTRICAS EXPUESTAS (prefijo 'predictiva_'):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. predictiva_request_latency_seconds (HISTOGRAM)
     - Buckets: [0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
     - Labels: method, endpoint
     - KPI: p99 < 5 segundos
     - Nota: buckets rodean el KPI para permitir histogram_quantile(0.99, ...) > 5

  2. predictiva_requests_total (COUNTER)
     - Incrementa por cada request HTTP (incluye HEAD, GET, POST, etc.)
     - Labels: method, endpoint, status_code
     - Útil para: calcular error rate (5xx / total)

  3. predictiva_request_errors_total (COUNTER)
     - Incrementa solo para status >= 400
     - Labels: method, endpoint, status_code
     - Nota: duplica info de requests_total pero simplifica algunas queries

CARDINALITY CONTROL (crítico para no explotar Prometheus):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⚠️  El label 'endpoint' es la RUTA TEMPLADA (ej. '/api/v1/forecast'), NO
      la ruta con path params sustituidos (ej. '/api/v1/forecast?id_well=POZO-001').
      La función _resolve_endpoint() hace esta conversión.

  ⚠️  Si NO templamos las rutas, un query param único por request = nuevo label
      value = EXPLOSIÓN DE SERIES (llamada "cardinality explosion").
      Ejemplo malo: '/api/v1/forecast?id_well=POZO-1' + '/api/v1/forecast?id_well=POZO-2'
      = 2 series distintas en lugar de 1.

  ✅ Mejor: '/api/v1/forecast' agrega ambas bajo el mismo label 'endpoint'.

EJEMPLO DE CUSTOM METRIC (para KPIs específicos de negocio):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Para contar 'forecasts generados':
    forecast_count = Counter(
        'predictiva_forecasts_generated_total',
        'Total de forecasts solicitados',
        ['status']  # 'success' | 'error'
    )
  En el endpoint POST /forecast:
    forecast_count.labels(status='success').inc()

  Query PromQL: sum(rate(predictiva_forecasts_generated_total[5m]))
  Dashboard: "Forecasts por segundo"

REFERENCIAS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  - docs/catedra/tutorial.md: Secciones 0, 1, 2
  - docs/decisions/0002-herramienta-de-metricas.md: ADR sobre Prometheus
  - https://prometheus.io/docs/instrumenting/writing_clientlibs/
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
    """Middleware ASGI puro que instrumenta cada request HTTP.

    Patrón ASGI puro (NO BaseHTTPMiddleware):
    - ✅ Permite leer status_code final sin consumir response body
    - ✅ No rompe streaming (datos grandes, SSE, WebSockets)
    - ✅ Más eficiente en memoria (no buffer todo el response)
    - ❌ Más bajo nivel (hay que manejar el ASGI scope/receive/send)

    Flujo:
    1. Capa aplicación (FastAPI) procesa request
    2. Antes del response: capturamos method, endpoint, start time
    3. Response se envía por el stream (send_wrapper)
    4. Cuando send({'type': 'http.response.start'}) pasa → leemos status_code
    5. Finalmente observamos latencia y actualizamos contadores
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
    """Ruta TEMPLADA (ej. '/api/v1/forecast') para agrupar series sin cardinalidad explosion.

    ⚠️  CARDINALITY CONTROL CRÍTICO:
        - Usa la ruta templada del router (FastAPI resuelve automáticamente)
        - Si usáramos scope['path'] crudamente, path params → label values distintos
        - Ejemplo: '/api/v1/forecast?id=POZO-1' vs '/api/v1/forecast?id=POZO-2'
          Sin templating: 2 series. Con templating: 1 serie agrupada.
        - Regla: < 100 valores por label. Más de eso → Prometheus sufre.

    Cuando el router no resolvió la ruta (404 por bot scans, paths inválidos)
    devolvemos un valor fijo "<unmatched>" para que TODOS los 404 queden bajo
    una sola serie en lugar de generar una serie por path crudo.
    """
    route = scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return "<unmatched>"


async def metrics_endpoint(_: Request) -> Response:
    """Handler del endpoint GET /metrics en formato text/plain Prometheus."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
