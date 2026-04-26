# Plataforma Predictiva - API Mock (Fase 1)

Este repositorio contiene la implementación inicial de la **Plataforma Predictiva** de producción de hidrocarburos desarrollada para la materia Ingeniería de Software (Groba, Salomon, Di Cola).

## Descripción

El objetivo de este servicio es proveer una API RESTful (Mock) que permite:
- Obtener un listado de pozos.
- Consultar pronósticos de producción para un horizonte de tiempo determinado.

Los resultados son estáticos o generados con lógicas simples a modo de maqueta para que los sistemas y equipos externos puedan integrarse de forma temprana.

## Componentes

El servicio se compone de cuatro contenedores que se levantan en simultáneo con Docker Compose:

| Servicio | Imagen | Puerto | Rol |
|----------|--------|--------|-----|
| `api` | build local (`Dockerfile`) | 8000 | API mock + endpoint `/metrics` para Prometheus |
| `prometheus` | `prom/prometheus:v2.54.1` | 9090 | TSDB que scrapea la API y el host (retención 15 días) |
| `grafana` | `grafana/grafana:11.2.0` | 3000 | Dashboards y alertas sobre los KPIs de la agenda |
| `node-exporter` | `prom/node-exporter:v1.7.0` | 9100 | Métricas de CPU, memoria y disco del host |

## Acceso

### Producción (instancia EC2)

Servicio público accesible vía DuckDNS en `api-hidraulicos-tipazos.duckdns.org`:

- Documentación interactiva (Swagger UI): http://api-hidraulicos-tipazos.duckdns.org:8000/docs
- Dashboard de monitoreo (Grafana): http://api-hidraulicos-tipazos.duckdns.org:3000 (usuario `admin`, contraseña `admin`)

Ejemplos:

```bash
# Listar pozos
curl -H "X-API-Key: abcdef12345" \
  "http://api-hidraulicos-tipazos.duckdns.org:8000/api/v1/wells?date_query=2026-04-26"

# Pedir pronóstico
curl -H "X-API-Key: abcdef12345" \
  "http://api-hidraulicos-tipazos.duckdns.org:8000/api/v1/forecast?id_well=POZO-001&date_start=2026-04-26&date_end=2026-04-30"
```

Sin el header `X-API-Key` los endpoints responden con HTTP 403 Forbidden.

### Local

Clonar el repo y desde la raíz:

```bash
docker compose up -d --build
```

Esto levanta los cuatro servicios. Una vez listos:

- API y Swagger UI: http://localhost:8000/docs
- Grafana: http://localhost:3000 (usuario `admin`, contraseña `admin` por defecto)
- Prometheus: http://localhost:9090
- Métricas de la API: http://localhost:8000/metrics
- Métricas del host: http://localhost:9100/metrics

Para apagar todo: `docker compose down`.

## Tests

Las pruebas unitarias usan `pytest` y `httpx` sobre el `TestClient` de FastAPI:

```bash
poetry install
poetry run pytest
```

El pipeline de CI (GitHub Actions) corre estos tests, un check de formato con Black y un build de imagen Docker antes de cada deploy.

## Tecnologías

- **Framework:** FastAPI (Python 3.10+)
- **Gestión de dependencias:** Poetry
- **Contenedores:** Docker + Docker Compose
- **CI/CD:** GitHub Actions (Pytest, Black, build de imagen, deploy SSH a EC2)
- **Observabilidad:** Prometheus + Grafana + node-exporter
- **Infraestructura:** AWS EC2 (Ubuntu t2.micro) + DuckDNS

## Decisiones de diseño

Los registros de decisiones arquitectónicas (ADR) están en [`docs/decisions/`](docs/decisions/). Documentamos ahí las opciones consideradas y los trade-offs detrás del stack tecnológico, la estrategia de contenedores, el monitoreo y las alertas.

La consigna y las agendas técnicas de la cátedra están en [`docs/catedra/`](docs/catedra/).
