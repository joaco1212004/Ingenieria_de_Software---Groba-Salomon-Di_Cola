# Plataforma Predictiva - Pronostico de Produccion de Pozos

Este repositorio contiene la Plataforma Predictiva completa: la API REST de pronosticos, el pipeline de datos medallion (Fase 2) y el loop de MLOps que entrena, versiona y sirve el modelo de declino (Fase 3).

## Descripcion

`GET /api/v1/forecast` devuelve **predicciones reales** de produccion mensual de petroleo por pozo: la API carga el modelo en stage `Production` del registry de MLflow y le suma las features del mart de gold. El pipeline de datos (Bronze S3 → dbt medallion → warehouse) y el de ML (features → training → gate → registry) corren orquestados por Dagster con particiones diarias.

## Arquitectura de la solucion

```text
datos.gob.ar ──> Bronze S3 ──> raw ──> silver ──> gold (estrella)      [Dagster + dbt]
                                                    │
                                    gold.fct_features_declino          [feature mart, ADR-0020]
                                                    │
              entrenamiento_m3 ──> validacion_m3 ──> registro_m3       [grupo ml, ADR-0022]
                     │                (gate log_mae,      │
                     │                 ADR-0024)          ▼
                     └────────> MLflow (EC2-2): runs + Model Registry  [ADR-0019]
                                                          │ stage Production
                                                          ▼
   Usuarios REST ──X-API-Key──> API /api/v1/forecast (EC2-1)           [serving online, ADR-0023]
                                  │  carga modelo Production (cache TTL 5 min)
                                  └─ features online del MISMO mart de gold
   Observabilidad: Prometheus + Grafana (EC2-1)  ·  BI Metabase + gobierno DataHub (EC2-2)
```

## Componentes

| Servicio | Imagen | Puerto | Rol |
|----------|--------|--------|-----|
| `api` | build local (`Dockerfile`) | 8000 | API de pronosticos (modelo Production del registry) + `/metrics` Prometheus |
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

### Serving de predicciones (Fase 3, ADR-0023)

`GET /api/v1/forecast?id_well=<sigla>&date_start=...&date_end=...` predice la
produccion mensual de petroleo del pozo para meses **futuros** (posteriores a
su ultimo dato):

- **Modelo**: carga `models:/declino-pozos-m3/Production` del registry MLflow
  con cache en memoria (TTL 5 min): un retrain promovido pasa a servirse solo,
  sin redeploy — la respuesta expone `model_version`.
- **Features online**: la serie historica de tasa diaria del pozo sale de
  `gold.fct_features_declino`, el mismo feature mart del training (ADR-0020):
  consistencia train/serve por construccion.
- **Unidades**: `prod` = tasa diaria predicha (m3/dia) x dias del mes
  (aproxima un mes de operacion completo); el campo `unit` lo explicita.
- **Errores explicitos** (sin fallback a historia): `400` rango invalido o que
  pisa la historia del pozo, `404` sigla inexistente, `503` sin modelo en
  Production / historia insuficiente / la curva de declino no ajusta.
- **Observabilidad**: `predictiva_forecasts_generated_total{status}` y
  `predictiva_model_version` en `/metrics`, ademas de la latencia HTTP
  (KPI p99 < 5 s).

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

### Entrenamiento ML (grupo `ml`, Fase 3)

El modelo de declino M3 (Arps + LSTM sobre el residual log, el mas robusto del
benchmark de investigacion DCA) se reentrena de forma recurrente con Dagster y
se trackea/registra en MLflow (ADR-0019 y ADR-0022):

- **Flujo**: `fct_produccion_pozo_mes` (gold) → `fct_features_declino` (feature
  mart dbt: tasa diaria `prod_pet / tef`, NULL en meses sin operar) →
  `entrenamiento_m3` → `validacion_m3` (gate champion/challenger por `log_mae`)
  → `registro_m3` (Model Registry: `None → Staging → Production`).
- **Job**: `ml_training_job`; schedule diario 07:00 ART (1h despues del
  medallion). Re-materializar una particion `fecha_extraccion` reentrena con la
  misma semilla y registra una version nueva: ese es el trigger de retrain.
- **Tracking**: cada run loggea params (hiperparametros + semilla + tamanos de
  cohorte), curvas de loss por epoca, medianas de test (`log_mae`, `rmse`,
  `err_acum_test`, `err_eur_gold`, R² de EUR) y el modelo como artefacto.
- **Clientes sin credenciales**: solo hace falta `MLFLOW_TRACKING_URI` (el
  server de MLflow en EC2-2 proxea los artefactos con `--serve-artifacts`).

Local: levantar MLflow junto al stack y correr el job para una particion:

```bash
docker compose -f infra/mlflow/docker-compose.mlflow.yml --env-file .env up -d
API_KEY=dev docker compose up -d --build
# Dagster UI (:3001) -> ml_training_job -> materializar la particion deseada
```

Para smoke runs, setear `ML_EPOCHS` / `ML_MAX_WELLS` en el `.env`.

### BI y Gobierno de datos (Fase 2)

BI (Metabase) y gobierno (DataHub) corren en una **segunda instancia (EC2-2)**
aparte del stack de datos, por su consumo de RAM. Se conectan al warehouse de
EC2-1. Detalle operativo en [`infra/datahub/README.md`](infra/datahub/README.md).

- **Metabase (BI):** `http://<EC2-2>:3000`. Usuarios no tecnicos exploran el
  schema `gold`. Dashboard de produccion por cuenca/empresa/periodo sobre
  `fct_produccion_pozo_mes` + dimensiones.
- **DataHub (gobierno):** `http://<EC2-2>:9002`. Catalogo del warehouse con
  `last_updated` por tabla, **lineage navegable a nivel tabla** (staging -> marts)
  y resultados de los dbt tests por tabla.

Topologia y deploy:

```text
EC2-1  api · postgres-dwh(warehouse) · dagster · prometheus · grafana · minio
EC2-2  metabase(:3000) + metabase-db   |   datahub web(:9002) · GMS(:8080)
       Metabase --query--> EC2-1:5432 (gold)
       Dagster/EC2-1 --ingest--> EC2-2:8080 (postgres + dbt metadata)
```

- **Exponer el warehouse a EC2-2:** en el `.env` de EC2-1 setear
  `POSTGRES_BIND=<ip-privada-EC2-1>` y abrir el inbound 5432 en el security group
  **solo desde EC2-2**. Variables de ejemplo en
  [`infra/platforms.env.example`](infra/platforms.env.example).
- **Deploy:** lo automatiza el workflow paralelo
  `.github/workflows/deploy-platforms.yml` (deploya EC2-2 y dispara la ingestion
  de metadata desde EC2-1). Manual: `scripts/datahub-up.sh` (EC2-2) +
  `docker compose -f infra/metabase/docker-compose.metabase.yml up -d` (EC2-2) +
  `scripts/datahub-ingest.sh` (EC2-1).

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
- Dagster + dagster-aws + dagster-dbt
- dbt + PostgreSQL (warehouse medallion)
- AWS S3 para Bronze
- MLflow (tracking + Model Registry) + PyTorch (LSTM) + scipy (Arps)
- Prometheus + Grafana + node-exporter
- Metabase (BI) + DataHub (gobierno)
- AWS EC2 + DuckDNS

## Decisiones de diseno

Los ADRs estan en `docs/decisions/`. Cubren CI/CD, dockerizacion, observabilidad, S3 Bronze, orquestacion Dagster, tipo de carga, warehouse, transformaciones, calidad, BI, gobierno de datos, y las decisiones de ML de la Fase 3: tracking/registry (0019), feature store (0020), enfoque de modelado (0021), orquestacion del retrain (0022), serving online (0023) y CI/CD del pipeline de ML con gate champion/challenger (0024). El mindmap de la Fase 3 esta en [`docs/adenda-3-mindmap.md`](docs/adenda-3-mindmap.md).
