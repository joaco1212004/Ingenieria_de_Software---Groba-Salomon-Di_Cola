# Calidad de datos con dbt tests + asset checks de Dagster

## Contexto y Declaración del Problema

La adenda fija tres MUST sobre calidad de datos:

1. Chequeos que cubran **mínimo 3 dimensiones** de las vistas en clase
   (schema, linaje, completitud, unicidad, frescura, …).
2. Los resultados **DEBEN quedar persistidos** — no alcanza con asserts
   en runtime.
3. Un check fallido **DEBE tener consecuencia operativa**: alerta,
   bloqueo de promoción aguas abajo, o marca de calidad visible.

Hay que elegir la herramienta y la política con la que se cumplen los
tres, sobre el stack ya decidido: Dagster
([ADR-0009](0009-orquestador-dagster.md)) orquestando dbt sobre Postgres
([ADR-0011](0011-transformacion-dbt-capas-medallion.md),
[ADR-0012](0012-warehouse-postgresql.md)).

## Factores de Decisión

- Persistencia de resultados consultable (en el warehouse, no en logs).
- Capacidad de **bloquear la promoción** silver → gold desde el
  orquestador.
- Cero servicios nuevos en una EC2 ya cargada.
- Declaratividad: los checks deben vivir junto a los modelos y revisarse
  en los mismos PRs.
- Cobertura de ambos mundos: archivos crudos (extracción, Python) y
  tablas (transformación, SQL).

## Opciones Consideradas

- **Opción A — dbt tests (+ `dbt-utils`/`dbt-expectations`) combinados
  con asset checks de Dagster.** dbt valida las tablas; Dagster valida la
  extracción y ejecuta el bloqueo operativo.
- **Opción B — Great Expectations.** Framework dedicado de calidad con
  suites, checkpoints y data docs.
- **Opción C — Soda Core.** Checks declarativos en SodaCL (YAML) contra
  el warehouse.
- **Opción D — Pandera.** Validación de esquemas sobre DataFrames de
  pandas.

## Resultado de la Decisión

**Opción elegida: A (dbt tests + asset checks de Dagster).**

**Por qué:**

- **Los checks viven donde viven los modelos:** cada test (`unique`,
  `not_null`, `accepted_values`, `relationships`,
  `dbt_utils.expression_is_true`, freshness de sources) se declara en el
  mismo YAML del modelo que valida y se revisa en el mismo PR. GE (B) y
  Soda (C) duplican esa definición en una configuración paralela que
  inevitablemente se desincroniza.
- **Persistencia sin infraestructura nueva (MUST 2):** dbt con
  `--store-failures` materializa las filas que fallan en tablas del
  esquema `audit` del warehouse, y un asset de Dagster parsea
  `run_results.json` a una tabla `audit.quality_results` (check, tabla,
  estado, timestamp, filas falladas). Ambas son consultables por SQL y
  desde Metabase — la "marca de calidad visible".
- **Consecuencia operativa real (MUST 3):** los **blocking asset checks**
  de Dagster condicionan la materialización aguas abajo: si falla un
  check sobre silver, **gold no se materializa** (bloqueo de promoción) y
  el run queda en estado fallido, visible en la UI y alertable con el
  stack existente ([ADR-0008](0008-grafana-para-dashboards-y-alertas.md)).
- **Cubre los dos mundos:** dbt testea tablas; los asset checks en Python
  validan lo que dbt no ve — el CSV crudo recién descargado (schema
  esperado de columnas, volumen mínimo por partición) antes de cargarlo.
- **Cero servicios nuevos:** B agrega un framework pesado con su propia
  noción de stores/checkpoints; C agrega un lenguaje (SodaCL) y un
  scheduler de scans. Ambos solapan ~80% con lo que dbt ya da gratis.

**Contra Pandera (D):** valida DataFrames en memoria, útil solo en la
extracción; no alcanza para tablas del warehouse, que es donde están los
MUST. Su rol lo cubren los asset checks de Dagster.

**Dimensiones de calidad cubiertas (≥3, MUST 1):**

| Dimensión | Check concreto |
|---|---|
| Schema | columnas/tipos esperados del CSV crudo (asset check) + `not_null` y contratos en dbt |
| Unicidad | `unique` sobre (idpozo, anio, mes) en silver — vigila la clave del merge ([ADR-0013](0013-tipo-de-carga-incremental-merge.md)) |
| Integridad referencial / linaje | `relationships` fact→dims + lineage dbt ingerido en DataHub ([ADR-0016](0016-gobierno-de-datos-datahub.md)) |
| Frescura | `dbt source freshness` sobre `fecha_data` / fecha de extracción |
| Completitud | volumen mínimo de filas por partición (asset check) |

### Consecuencias

- **Bueno, porque:** resultados de calidad consultables en el warehouse y
  graficables en Metabase; un fail bloquea gold y dispara alerta — los
  tres MUST cubiertos con herramientas que ya están en el stack.
- **Bueno, porque:** los tests corren también en CI (`dbt build` incluye
  los tests) — la calidad se valida antes del merge del PR, no solo en
  producción.
- **Malo, porque:** persistir `run_results.json` requiere un parser
  propio pequeño (no viene resuelto out-of-the-box).
- **Malo, porque:** no tendremos los data docs/HTML vistosos de Great
  Expectations; lo aceptamos porque la visibilidad exigida la dan
  Metabase y la UI de Dagster.

### Confirmación

Se verifica con: las tablas `audit.quality_results` y las de
`store_failures` pobladas tras un run; una demo donde un check forzado a
fallar **bloquea** la materialización de gold y genera alerta; y la tabla
de dimensiones de calidad de arriba trazable a tests concretos en el repo.
