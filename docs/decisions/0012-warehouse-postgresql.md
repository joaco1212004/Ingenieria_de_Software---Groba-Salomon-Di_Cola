# PostgreSQL como motor del data warehouse

## Contexto y Declaración del Problema

La adenda exige un **data warehouse con modelo estrella**
([ADR-0014](0014-modelo-dimensional-estrella.md)) que será consultado por
la plataforma de BI ([ADR-0017](0017-bi-metabase.md)), catalogado por la
plataforma de gobierno ([ADR-0016](0016-gobierno-de-datos-datahub.md)) y,
a futuro, por la API de pronóstico de la Fase 1. Las capas silver y gold
viven ahí, transformadas por dbt
([ADR-0011](0011-transformacion-dbt-capas-medallion.md)).

El volumen real es moderado: los CSVs fuente suman del orden de 1–2
millones de filas — no es big data. Hay que elegir el motor.

## Factores de Decisión

- Costo sobre los créditos de AWS Academy.
- Acceso concurrente de múltiples servicios: dbt escribe; Metabase,
  DataHub y la API leen, todos a la vez.
- Integración de primera clase con el stack elegido (dbt, Metabase,
  DataHub).
- Operación dentro del Docker Compose existente
  ([ADR-0003](0003-docker-compose-para-orquestacion.md)) y desarrollo
  local sin credenciales.
- Adecuación al volumen real (~10⁶ filas), sin sobredimensionar.

## Opciones Consideradas

- **Opción A — PostgreSQL en Docker Compose.** Un contenedor `postgres`
  con volumen persistente, esquemas `staging` (silver) y `marts` (gold).
- **Opción B — DuckDB sobre parquet en S3.** Silver/gold como archivos
  parquet en el mismo bucket del lake; DuckDB como motor de consulta
  embebido.
- **Opción C — Redshift o Athena (AWS).** Warehouse analítico gestionado
  por AWS.

## Resultado de la Decisión

**Opción elegida: A (PostgreSQL en Docker Compose).**

**Por qué:**

- **Es cliente-servidor, y eso es lo que el sistema necesita:** Metabase,
  DataHub, dbt y la API se conectan concurrentemente al mismo endpoint.
  DuckDB (B) es una librería embebida in-process con un solo escritor:
  compartir el mismo warehouse entre cuatro servicios en contenedores
  distintos se vuelve artesanal (archivos compartidos, locks) justo donde
  necesitamos que sea aburrido.
- **Integración de primera clase con todo el stack:** `dbt-postgres`,
  el conector Postgres de Metabase y la ingestión Postgres de DataHub son
  los caminos más probados de cada herramienta. Con DuckDB cada
  integración es el caso raro; con Athena cada herramienta necesita
  drivers y permisos de AWS.
- **Costo cero y operación conocida:** un contenedor más en el compose
  que el equipo ya opera ([ADR-0003](0003-docker-compose-para-orquestacion.md)),
  levantable en local con `docker compose up`. Redshift consume créditos
  de Academy por hora de cluster y Athena cobra por query escaneada;
  ambos atan al proveedor y exigen credenciales hasta para desarrollar.
- **El volumen no justifica un motor columnar:** 1–2 millones de filas
  con índices razonables se consultan en milisegundos-segundos en
  Postgres. Elegir Redshift acá es sobredimensionar.

### Consecuencias

- **Bueno, porque:** todos los servicios apuntan a un único host:puerto
  dentro de la red del compose; backups simples vía `pg_dump`; el mismo
  stack corre idéntico en CI (Postgres efímero) y en local.
- **Bueno, porque:** la API de la Fase 1 puede evolucionar de respuestas
  mock a leer del warehouse sin cambiar de infraestructura.
- **Malo, porque:** Postgres es row-store: agregaciones analíticas sobre
  toda la fact serán más lentas que en un motor columnar. Al volumen
  actual es irrelevante; si creciera órdenes de magnitud, este ADR se
  revisa (la salida natural sería B o C).
- **Malo, porque:** suma ~200–300 MB de RAM y disco EBS a la EC2
  (mitigado: bronze queda en S3, el warehouse solo aloja silver/gold).

### Confirmación

Se verifica con: el servicio `postgres-dwh` en `docker-compose.yml` con
volumen persistente; el profile de dbt apuntando a él; Metabase y DataHub
conectados al mismo endpoint; y el integration test del CI validando
filas en `marts` tras materializar el pipeline.
