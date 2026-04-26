# Prometheus para métricas de la API

## Contexto y Declaración del Problema

La adenda técnica exige un dashboard técnico de monitoreo que cubra, entre
otras, **latencia de pronóstico (KPI < 5s)**, **disponibilidad de la API
(KPI 99.5% uptime)** y **frecuencia de consulta de la API REST por
sistemas externos**. Estas tres métricas son a nivel **aplicación**: viven
adentro del proceso de FastAPI, dependen del request handler que las
emite, y no se pueden derivar mirando exclusivamente la VM.

Necesitamos elegir un sistema que (a) reciba métricas tipo counter,
histogram y gauge desde la app, (b) las almacene como time-series, y (c)
sirva como datasource para el dashboard de visualización (definido en el
[ADR-0008](0008-grafana-para-dashboards-y-alertas.md)).

## Factores de Decisión

- Esfuerzo de instrumentación dentro del código FastAPI.
- Versionado de la configuración del scraper junto al resto de la infra.
- Costo monetario sobre los créditos de AWS Academy.
- Independencia del cloud provider (la app debe ser desplegable fuera de
  AWS si en una fase futura migramos).
- Desarrollo y testeo en local sin necesidad de credenciales AWS.

## Opciones Consideradas

- **Opción A — Prometheus self-hosted en Docker Compose.** Instrumentamos
  FastAPI con `prometheus-client`, exponemos el endpoint `/metrics`, y
  Prometheus lo scrapea desde un servicio adicional del compose en EC2.
- **Opción B — Amazon CloudWatch Metrics.** Publicamos métricas custom
  desde la app con boto3 (`PutMetricData`).
- **Opción C — Servicio gestionado de Prometheus (Amazon Managed Service
  for Prometheus, AMP).** Prometheus como servicio de AWS, sin
  administrar el binario.

## Resultado de la Decisión

**Opción elegida: A (Prometheus self-hosted en Docker Compose).**

**Por qué:**

- **Modelo pull encaja perfecto con Compose:** la API expone `/metrics`,
  Prometheus está en la misma red Docker (definida por compose) y le
  hace scraping cada 15 segundos. No hace falta que la app conozca la
  existencia del sistema de monitoreo, ni que tenga credenciales AWS, ni
  que haga llamadas salientes que puedan fallar de formas raras (timeouts,
  rate limits de la SDK).
- **Versionable:** la configuración del scrape (`prometheus.yml`) y las
  reglas de alerta viven en el repo. Un PR que cambia métricas y reglas se
  revisa atómicamente. CloudWatch Metrics es agnóstico al repo: las
  métricas custom existen sólo cuando se publica el primer datapoint.
- **Costo cero en créditos AWS Academy:** Prometheus corre dentro de la
  misma EC2 t2.micro. CloudWatch cobra por métrica custom publicada por
  mes (aunque la primera tier sea barata, las dimensiones disparan el
  costo) y AMP cobra por sample ingerido.
- **Independencia de proveedor:** `prometheus-client` es estándar de
  facto; las mismas métricas funcionan idénticas si en una fase futura
  movemos el cómputo a EKS, Fargate o cualquier otra plataforma. Con
  CloudWatch quedaríamos atados a AWS.
- **Desarrollo local:** todos los miembros del equipo pueden levantar
  Prometheus + la API con un `docker compose up`, sin credenciales AWS.
  Esto reduce la fricción para depurar dashboards y reglas localmente.

### Consecuencias

- **Bueno, porque:** las métricas de aplicación son agnósticas al
  proveedor cloud y reutilizables en cualquier entorno; el endpoint
  `/metrics` es testeable como cualquier otro endpoint HTTP en pytest;
  toda la observabilidad cabe en el mismo `docker-compose.yml`.
- **Malo, porque:** Prometheus corre en la misma t2.micro que la API. Si
  la VM cae, perdemos la herramienta de observación junto con el
  observado. Para un mock de Fase 1 es aceptable; mitigamos parcialmente
  con alertas externas en fases posteriores.
- **Malo, porque:** la retención de Prometheus es local al volumen del
  contenedor. Si la EC2 se reinicia y el volumen no es persistente, los
  datos históricos se pierden. Lo aceptamos porque la métrica que importa
  realmente para la entrega es **el estado actual**, no series largas.

### Confirmación

Se verifica con la presencia del servicio `prometheus` en
`docker-compose.yml`, el endpoint `/metrics` expuesto por
[`api/metrics.py`](../../api/metrics.py) en la API, y dashboards en Grafana
que consultan correctamente el datasource de Prometheus durante la demo de
Fase 1.