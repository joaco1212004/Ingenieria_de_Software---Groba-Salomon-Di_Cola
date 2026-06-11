# dbt orquestado por Dagster para las transformaciones medallion

## Contexto y Declaración del Problema

Con bronze resuelto en S3 ([ADR-0010](0010-datalake-bronze-s3.md)) y el
warehouse en PostgreSQL ([ADR-0012](0012-warehouse-postgresql.md)), falta
decidir **con qué motor se transforman los datos** bronze → silver
(limpieza, tipado, deduplicación) → gold (modelo estrella,
[ADR-0014](0014-modelo-dimensional-estrella.md)).

La elección condiciona varios MUST de la adenda: el **lineage** navegable
en la plataforma de gobierno, los **chequeos de calidad persistidos**
([ADR-0015](0015-calidad-de-datos-dbt-tests.md)), la **documentación del
modelo de datos**, y el bonus de **semantic layer**.

## Factores de Decisión

- Lineage automático entre tablas, exportable a DataHub (MUST de
  gobierno).
- Tests de datos integrados y persistibles (MUST de calidad).
- Generación de documentación del modelo de datos (MUST).
- Integración con el orquestador Dagster
  ([ADR-0009](0009-orquestador-dagster.md)).
- Dónde ocurre el cómputo: los datos de silver/gold viven en Postgres;
  moverlos a memoria de Python para devolverlos es trabajo doble.
- Habilitar el bonus de semantic layer sin herramienta adicional.

## Opciones Consideradas

- **Opción A — dbt-core orquestado con `dagster-dbt`.** Las
  transformaciones son modelos SQL versionados; dbt resuelve el orden con
  `ref()` y Dagster materializa cada modelo como un asset.
- **Opción B — Python/pandas dentro de assets de Dagster.** Cada
  transformación lee de Postgres/S3 a un DataFrame y escribe el
  resultado.
- **Opción C — Scripts SQL planos ejecutados por Dagster.** Archivos
  `.sql` versionados que un asset ejecuta contra Postgres en orden
  hardcodeado.

## Resultado de la Decisión

**Opción elegida: A (dbt-core + `dagster-dbt`).**

**Por qué:**

- **Lineage gratis y exportable:** `ref()` construye el DAG de modelos;
  la ingestión de dbt a DataHub publica ese lineage tabla→tabla y la
  documentación de columnas, cumpliendo el MUST de lineage navegable sin
  código propio. Con B o C el lineage habría que declararlo a mano y
  mantenerlo sincronizado.
- **Calidad declarativa y persistible:** los dbt tests (`unique`,
  `not_null`, `relationships`, más `dbt-utils`/`dbt-expectations`) viven
  junto a cada modelo y con `--store-failures` persisten las filas
  fallidas en el warehouse — la base del
  [ADR-0015](0015-calidad-de-datos-dbt-tests.md).
- **Documentación del modelo incluida:** `dbt docs` genera el catálogo de
  modelos, columnas y descripciones a partir de los mismos YAML que
  definen los tests; es la mitad de la doc del modelo de datos exigida.
- **El cómputo queda en el warehouse:** dbt compila SQL que Postgres
  ejecuta in-situ (ELT). Con pandas (B) cada corrida saca cientos de
  miles de filas a la RAM de la EC2 para devolverlas transformadas:
  ineficiente y frágil en una instancia chica.
- **Integración oficial con Dagster:** `dagster-dbt` mapea cada modelo a
  un asset con su status, logs y particiones, manteniendo la
  observabilidad de todo el pipeline en una sola UI.
- **Habilita el bonus:** el semantic layer de dbt (MetricFlow) define
  métricas de negocio una sola vez sobre los modelos ya existentes, sin
  herramienta nueva.

**Contra las alternativas:** pandas (B) es más familiar pero convierte
cada MUST (lineage, tests persistidos, docs) en código artesanal a
mantener; queda reservado para la **extracción** (bronze), donde sí es la
herramienta natural. SQL plano (C) evita la dependencia pero nos obliga a
reimplementar mal lo que dbt ya resuelve: orden de dependencias, tests,
docs y lineage.

### Consecuencias

- **Bueno, porque:** separación de responsabilidades nítida — Dagster
  mueve archivos y orquesta; dbt transforma dentro del warehouse; cada
  capa medallion es un directorio de modelos (`staging/` = silver,
  `marts/` = gold) revisable en PRs.
- **Bueno, porque:** los modelos dbt se testean en CI con `dbt build`
  contra un Postgres efímero, dentro del job `test` existente.
- **Malo, porque:** dbt es otra herramienta con curva propia (Jinja en
  SQL, profiles, materializaciones) y agrega peso a la imagen Docker del
  orquestador.
- **Malo, porque:** dbt solo transforma *dentro* del warehouse: el salto
  S3 → Postgres (carga de bronze a staging) sigue siendo responsabilidad
  de un asset Python de Dagster.

### Confirmación

Se verifica con: el proyecto dbt en el repo con modelos `staging/` y
`marts/` y sus YAML de tests/docs; los modelos apareciendo como assets en
la UI de Dagster vía `dagster-dbt`; `dbt docs generate` produciendo el
catálogo; y el lineage de modelos visible en DataHub tras la ingestión.
