# DataHub como plataforma de gobierno de datos

## Contexto y Declaración del Problema

La adenda exige una **plataforma de gobierno de datos** donde se puedan
ver: los workflows de extracción, los datos del warehouse y la última vez
que fueron actualizados; con **lineage navegable a nivel tabla**. Además
fija el marco de la decisión: "DEBE estar implementada con alguna
herramienta vista en clase o tutoría (**DataHub**). PUEDEN explorar
alternativas si está debidamente justificado" — es decir, apartarse de
DataHub tiene carga de justificación extra.

Las fuentes de metadata son el stack ya decidido: Postgres
([ADR-0012](0012-warehouse-postgresql.md)), dbt
([ADR-0011](0011-transformacion-dbt-capas-medallion.md)) y Dagster
([ADR-0009](0009-orquestador-dagster.md)).

## Factores de Decisión

- Cumplimiento de los tres puntos del MUST (workflows, datos, última
  actualización) y del lineage a nivel tabla.
- Conectores existentes para Postgres, dbt y S3 (no escribir ingestión a
  mano).
- Carga de justificación: la adenda ya señala DataHub como el camino
  visto en tutoría.
- Peso operativo: qué le hace a la infraestructura del equipo.
- Configuración versionable en el repo.

## Opciones Consideradas

- **Opción A — DataHub.** Catálogo + lineage + glosario; ingestión
  declarativa vía *recipes* YAML.
- **Opción B — OpenMetadata.** Catálogo open source comparable a DataHub
  en features.
- **Opción C — Marquez (OpenLineage) o Amundsen.** Herramientas más
  acotadas: Marquez es lineage puro; Amundsen es catálogo/discovery con
  lineage limitado.

## Resultado de la Decisión

**Opción elegida: A (DataHub).**

**Por qué:**

- **Es la herramienta vista en tutoría:** la adenda invierte la carga de
  la prueba — cualquier otra opción exige justificación adicional, y ni B
  ni C ofrecen un beneficio diferencial que la pague.
- **Cubre los tres puntos del MUST con conectores estándar:** la
  ingestión de Postgres cataloga las tablas del warehouse con su
  `last updated`; la ingestión de **dbt** publica el lineage
  tabla→tabla (de `staging` a `marts`) y los resultados de tests; la
  integración con Dagster expone los workflows de extracción. Todo con
  *recipes* YAML **versionadas en el repo**, coherente con cómo
  versionamos el resto de la configuración
  ([ADR-0006](0006-prometheus-para-metricas-de-la-api.md)).
- **Lineage a nivel tabla navegable en la UI** — el requisito explícito —
  más glosario de negocio y ownership por dataset, que alimentan el
  trabajo de los roles definidos en
  [ADR-0018](0018-roles-del-equipo.md).

**Contra las alternativas:** OpenMetadata (B) es técnicamente comparable
(quizás más liviano), pero al no ser la herramienta de la tutoría
tendríamos que justificar el desvío sin ganar nada distintivo. Marquez (C)
solo resuelve lineage de runs: no es un catálogo ni muestra glosario/última
actualización por tabla. Amundsen está pensado para discovery, su lineage
es limitado y el proyecto tiene menos actividad.

### Consecuencias

- **Malo (y lo declaramos honestamente), porque DataHub es pesado:** su
  quickstart levanta GMS, frontend, MySQL, Elasticsearch y Kafka —
  del orden de 6–8 GB de RAM. **No entra en la EC2 actual junto al stack
  existente.** Mitigación elegida: DataHub corre en un
  `docker-compose.datahub.yml` separado, levantado **on-demand** (demo y
  sesiones de gobierno) en una máquina del equipo o en una segunda
  instancia si los créditos lo permiten; como la ingestión por recipes es
  idempotente, re-poblarlo tras cada arranque es un comando.
- **Bueno, porque:** las recipes en el repo hacen la metadata
  reproducible: cualquier integrante regenera el catálogo completo con
  `datahub ingest -c <recipe>`.
- **Bueno, porque:** los resultados de dbt tests visibles por tabla en
  DataHub refuerzan la "marca de calidad visible" del
  [ADR-0015](0015-calidad-de-datos-dbt-tests.md).
- **Malo, porque:** es una pieza más que aprender y demo-ear; acotamos el
  alcance a lo exigido (catálogo, lineage, frescura, glosario mínimo).

### Confirmación

Se verifica con: `docker-compose.datahub.yml` y las recipes de ingestión
(Postgres, dbt) versionadas en el repo; una demo navegando el lineage
tabla→tabla desde `staging` hasta `marts`; la fecha de última
actualización visible por tabla; y las instrucciones de acceso en el
`README.md` (requisito no funcional de la adenda).
