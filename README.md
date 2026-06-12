# Plataforma Predictiva - API Mock e Integracion de Datos

Este repositorio contiene la API REST mock de la Plataforma Predictiva y la primera implementacion de integracion de datos pedida para la Fase 2.

## Descripcion

El servicio expone endpoints de pozos y forecast para integraciones tempranas. La Fase 2 suma una capa Bronze en S3, orquestada con Dagster, para aterrizar los CSV crudos de datos.gob.ar bajo una arquitectura medallion.

## Componentes

| Servicio | Imagen | Puerto | Rol |
|----------|--------|--------|-----|
| `api` | build local (`Dockerfile`) | 8000 | API mock + endpoint `/metrics` para Prometheus |
| `dagster-code-server` | build local (`Dockerfile`) | interno | Carga el modulo `pipeline.definitions` una sola vez para webserver y daemon |
| `dagster-webserver` | build local (`Dockerfile`) | 3001 | UI de gobierno tecnico del pipeline: runs, logs, assets, particiones y status |
| `dagster-daemon` | build local (`Dockerfile`) | - | Scheduler de Dagster para ejecutar el job Bronze diario |
| `prometheus` | `prom/prometheus:v2.54.1` | 9090 | TSDB que scrapea la API y el host |
| `grafana` | `grafana/grafana:11.2.0` | 3000 | Dashboards y alertas de monitoreo |
| `node-exporter` | `prom/node-exporter:v1.7.0` | 9100 | Metricas de CPU, memoria y disco del host |
| `minio` | `minio/minio` | 9000 / 9001 | Doble local de S3 para desarrollo e integration tests |

## Acceso

### Produccion (instancia EC2)

Servicio publico accesible via DuckDNS en `api-hidraulicos-tipazos.duckdns.org`:

- Swagger UI: http://api-hidraulicos-tipazos.duckdns.org:8000/docs
- Grafana: http://api-hidraulicos-tipazos.duckdns.org:3000 (usuario `admin`, contrasena `admin`)
- Dagster UI: http://api-hidraulicos-tipazos.duckdns.org:3001

Ejemplos, asumiendo que la API key esta en `API_KEY`:

```bash
curl -H 'X-API-Key: $API_KEY' \
  'http://api-hidraulicos-tipazos.duckdns.org:8000/api/v1/wells?date_query=2026-04-26'

curl -H 'X-API-Key: $API_KEY' \
  'http://api-hidraulicos-tipazos.duckdns.org:8000/api/v1/forecast?id_well=POZO-001&date_start=2026-04-26&date_end=2026-04-30'
```

Sin el header `X-API-Key` los endpoints responden HTTP 403. La API key vive en el `.env` no commiteado de la EC2.

### Bronze en S3

La capa Bronze escribe snapshots crudos en S3 con layout particionado:

```text
s3://<bucket>/datalake/bronze/<dataset>/fecha_extraccion=YYYY-MM-DD/<archivo>.csv
```

Datasets materializados:

- `listado_pozos_bronze`: listado de pozos cargados por empresas operadoras.
- `produccion_no_convencional_bronze`: produccion de pozos de gas y petroleo no convencional.

En produccion, el `.env` no commiteado de la EC2 debe tener:

```bash
BRONZE_BUCKET=<bucket-bronze>
S3_ENDPOINT_URL=
AWS_ACCESS_KEY_ID=<credencial-temporal>
AWS_SECRET_ACCESS_KEY=<credencial-temporal>
AWS_SESSION_TOKEN=<credencial-temporal>
AWS_DEFAULT_REGION=<region>
```

`S3_ENDPOINT_URL` queda vacio para usar S3 real. En local, Docker Compose usa MinIO por defecto.

### Orquestacion y backfill

Dagster define los workflows como codigo en `pipeline/assets/` y `pipeline/definitions.py`.

- Job: `bronze_daily_job`.
- Schedule: `bronze_daily_schedule`, todos los dias a las 06:00 `America/Argentina/Buenos_Aires`.
- Idempotencia: re-materializar una particion sobrescribe el mismo objeto S3 de esa `fecha_extraccion`.
- Retries: cada asset Bronze tiene `RetryPolicy` con 3 reintentos y backoff exponencial.
- Observabilidad: Dagster UI muestra runs, logs, assets, particiones y estado.

Para reprocesar una fecha puntual desde la EC2:

```bash
cd ~/Ingenieria_de_Software---Groba-Salomon-Di_Cola
bash scripts/materialize-bronze.sh YYYY-MM-DD
```

Tambien se puede lanzar/backfillear desde la UI de Dagster seleccionando las particiones del grupo `bronze`.

### Local

Desde la raiz:

```bash
API_KEY=dev docker compose up -d --build
```

Servicios locales:

- API y Swagger UI: http://localhost:8000/docs
- Dagster UI: http://localhost:3001
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090
- MinIO Console: http://localhost:9001

Para apagar todo:

```bash
docker compose down
```

## Actualizar workflows

Los workflows de datos se actualizan modificando los assets en `pipeline/assets/` y registrandolos en `pipeline/definitions.py`. Todo cambio debe pasar por PR: el CI ejecuta tests unitarios de API, tests Bronze con S3 mockeado por `moto`, Black, build Docker e integration test.

## Tests

```bash
poetry install
poetry run black --check .
poetry run pytest
```

## Tecnologias

- FastAPI
- Poetry
- Docker + Docker Compose
- GitHub Actions
- Dagster + dagster-aws
- AWS S3 para Bronze
- Prometheus + Grafana + node-exporter
- AWS EC2 + DuckDNS

## Decisiones de diseno

Los ADRs estan en `docs/decisions/`. Cubren CI/CD, dockerizacion, observabilidad, S3 Bronze, orquestacion Dagster, tipo de carga, warehouse, transformaciones, calidad, BI y gobierno de datos.
