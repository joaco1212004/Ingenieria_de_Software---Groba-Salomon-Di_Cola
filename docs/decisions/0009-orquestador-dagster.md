# Dagster como orquestador de DAGs

## Contexto y Declaración del Problema

La Adenda 2 exige una herramienta de orquestación con **DAGs definidos como
código** (menciona "Airflow / Prefect / Dagster / equivalente") y agrega
requisitos duros sobre esos DAGs: **idempotencia**, **retries con backoff**,
**observabilidad mínima** (logs y status accesibles) y un **procedimiento
documentado y verificable de backfill**.

El pipeline a orquestar es: extracción de los dos CSVs de datos.gob.ar →
capa bronze en S3 ([ADR-0010](0010-datalake-bronze-s3.md)) →
transformaciones silver/gold con dbt
([ADR-0011](0011-transformacion-dbt-capas-medallion.md)) → warehouse
PostgreSQL ([ADR-0012](0012-warehouse-postgresql.md)) → ingestión de
metadata a DataHub ([ADR-0016](0016-gobierno-de-datos-datahub.md)).

## Factores de Decisión

- Cumplimiento directo de los MUST: idempotencia, retries con backoff,
  observabilidad, backfill.
- Testeabilidad en pytest dentro del job `test` del CI existente
  ([ADR-0004](0004-ci-con-github-actions.md)), sin levantar servicios.
- Footprint de RAM/CPU: corre en la misma EC2 con Docker Compose que el
  resto del stack ([ADR-0003](0003-docker-compose-para-orquestacion.md)).
- Integración con dbt (la herramienta de transformación elegida) y con
  DataHub (lineage).
- Curva de aprendizaje para un equipo de 3 personas con poco tiempo.

## Opciones Consideradas

- **Opción A — Dagster.** Orquestador centrado en *software-defined
  assets*: cada dataset (CSV en bronze, tabla silver, tabla gold) se
  declara como un asset Python con sus dependencias, particiones y
  políticas de retry.
- **Opción B — Apache Airflow.** El estándar industrial de orquestación,
  centrado en tasks y operators, con scheduler + webserver + metadata DB.
- **Opción C — Prefect.** Orquestador pythonic centrado en *flows* y
  *tasks*, con servidor open source y oferta cloud.
- **Opción D — cron + scripts.** Scripts de extracción/transformación
  disparados por crontab en la EC2.

## Resultado de la Decisión

**Opción elegida: A (Dagster).**

**Por qué:**

- **Backfill e idempotencia son nativos:** Dagster modela los assets con
  **particiones por fecha**. Re-materializar la partición
  `2026-06-01` sobrescribe exactamente esa partición — correrla dos veces
  da el mismo resultado (idempotencia) y el backfill histórico es
  seleccionar un rango de particiones desde la UI o el CLI
  (`dagster job backfill`). En Airflow esto existe vía `execution_date`
  pero la semántica es implícita y famosa por sus confusiones; en Prefect
  el particionado hay que armarlo a mano.
- **Retries con backoff declarativos:** `RetryPolicy(max_retries=3,
  delay=..., backoff=Backoff.EXPONENTIAL)` se declara en el código del
  asset y queda versionado en el repo, cumpliendo el MUST sin
  configuración externa.
- **Observabilidad incluida:** la UI de Dagster (webserver) muestra runs,
  logs estructurados por asset, status de cada partición y el grafo de
  lineage — cumple "logs y status accesibles" sin servicios adicionales.
- **Testeable in-process en pytest:** `materialize([...])` ejecuta assets
  dentro del proceso de test, sin scheduler ni base de metadata. Los
  tests del pipeline entran en el job `test` del CI existente igual que
  los de la API; S3 se mockea con `moto`. Testear un DAG de Airflow exige
  inicializar su metadata DB y es notoriamente incómodo.
- **Integración oficial con dbt:** `dagster-dbt` mapea cada modelo dbt a
  un asset, con lo cual el lineage bronze→silver→gold queda completo en
  una sola UI y es exportable a DataHub.
- **Más liviano que Airflow:** dos procesos (webserver + daemon) contra
  scheduler + webserver + workers (+ redis/celery para escalar). Importa
  porque conviven con la API, Prometheus y Grafana en la misma instancia.

**Contra las alternativas:** Airflow (B) es el estándar pero paga su
generalidad en RAM, en fricción de testing y en una semántica de
particiones menos explícita. Prefect (C) es liviano y agradable, pero su
modelo de flows no es asset-céntrico (el lineage habría que construirlo a
mano para DataHub) y las features de particiones/backfill maduras empujan
hacia Prefect Cloud (SaaS). cron (D) no cumple ninguno de los MUST: no hay
DAG, ni retries declarativos, ni UI de status, ni backfill.

### Consecuencias

- **Bueno, porque:** los MUST de la adenda (idempotencia, retries,
  observabilidad, backfill) se cumplen con primitivas nativas y
  versionadas en el repo, no con convenciones manuales.
- **Bueno, porque:** los assets se testean en pytest dentro del pipeline
  de CI existente, y el integration test puede materializar el DAG
  end-to-end contra MinIO + Postgres en Docker Compose.
- **Malo, porque:** webserver + daemon suman del orden de 0.5–1 GB de RAM
  al compose; hay que dimensionar la EC2 o separar servicios.
- **Malo, porque:** Dagster introduce conceptos propios (assets,
  partitions, IO managers, resources) que el equipo debe aprender, y sus
  releases son frecuentes (pinneamos versión en `pyproject.toml`).

### Confirmación

Se verifica con: el paquete del pipeline en el repo definiendo assets con
`RetryPolicy` y particiones diarias/mensuales; runs y logs visibles en la
UI de Dagster durante la demo; el procedimiento de backfill documentado en
el runbook del data engineer y ejecutado sobre una partición histórica; y
tests de assets corriendo en el job `test` del CI.
