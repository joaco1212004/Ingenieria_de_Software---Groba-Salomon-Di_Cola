# Tipo de carga: snapshot full en bronze, merge idempotente en silver/gold

## Contexto y Declaración del Problema

La adenda exige **definir y justificar explícitamente el tipo de carga
(full / incremental append / merge / upsert) en un ADR**, junto con dos
MUST relacionados: el procesamiento debe ser **idempotente** y debe ser
posible **reprocesar los datos de una fecha** si hay cambios.

Las características de la fuente mandan:

- datos.gob.ar **no ofrece deltas ni API incremental**: cada descarga es
  el CSV completo del dataset.
- Los datos **se rectifican retroactivamente**: el dataset de producción
  trae la columna `rectificado`, es decir que una fila de un período
  pasado puede cambiar en una publicación posterior.
- El grano natural es (idpozo, anio, mes) para producción y (idpozo) para
  el listado de pozos.

La decisión no es única para todo el pipeline: cada capa medallion tiene
necesidades distintas, así que se define **por capa**.

## Factores de Decisión

- La fuente solo entrega archivos completos (restricción dura).
- Correcciones retroactivas deben absorberse sin intervención manual.
- Idempotencia: correr dos veces la misma carga = mismo resultado (MUST).
- Reprocesamiento por fecha verificable (MUST), alineado con las
  particiones de Dagster ([ADR-0009](0009-orquestador-dagster.md)).
- Auditabilidad: poder responder "¿qué decía la fuente el día X?".
- Costo de cómputo creciente con el histórico.

## Opciones Consideradas

- **Opción A — Full reload en todas las capas.** Cada corrida trunca y
  recarga bronze, silver y gold desde cero.
- **Opción B — Incremental append.** Cada corrida agrega lo descargado a
  continuación de lo existente, en todas las capas.
- **Opción C — Híbrido: snapshot full append-only en bronze +
  merge/upsert (delete+insert por clave) en silver y gold.**

## Resultado de la Decisión

**Opción elegida: C (snapshot full inmutable en bronze, merge idempotente
en silver/gold).**

**Por capa:**

- **Bronze (full snapshot, append-only por partición):** cada extracción
  guarda el CSV completo bajo
  `bronze/<dataset>/fecha_extraccion=YYYY-MM-DD/`
  ([ADR-0010](0010-datalake-bronze-s3.md)). Nunca se modifica un snapshot
  existente; re-correr la extracción de una fecha sobrescribe íntegra esa
  partición (idempotente). Esto preserva la auditoría: cada versión
  publicada por la fuente queda archivada.
- **Silver (merge/upsert):** modelos dbt incrementales con estrategia
  `delete+insert` por clave natural — (idpozo, anio, mes) en producción,
  (idpozo) en pozos. La corrida procesa el último snapshot y **pisa** las
  filas de las claves presentes: las rectificaciones retroactivas de la
  fuente se absorben solas, y repetir la corrida da el mismo estado
  final.
- **Gold (merge desde silver):** las dimensiones se upsertean por clave
  natural (SCD tipo 1, [ADR-0014](0014-modelo-dimensional-estrella.md)) y
  la fact se reconstruye por partición de período desde silver, también
  idempotente.

**Contra las alternativas:**

- **Full reload total (A)** es simple e idempotente, pero (1) pierde el
  historial de snapshots — imposible auditar qué decía la fuente antes de
  una rectificación —, (2) hace que "reprocesar una fecha" no exista como
  operación: solo existe reprocesar *todo*, lo que vacía de sentido el
  MUST de backfill por fecha, y (3) su costo crece con el histórico
  completo en cada corrida diaria/mensual.
- **Append puro (B)** rompe contra esta fuente: como cada publicación
  trae el dataset completo y rectificado, apendear duplica todas las
  filas en cada corrida y delega la deduplicación a todos los
  consumidores aguas abajo. Viola la idempotencia (dos corridas = doble
  de filas) y el test de unicidad de la clave
  ([ADR-0015](0015-calidad-de-datos-dbt-tests.md)).

### Consecuencias

- **Bueno, porque:** el backfill exigido queda definido de forma
  verificable: re-materializar la partición de Dagster de una fecha
  re-descarga (o relee) el snapshot y el merge deja silver/gold en el
  estado correcto, sin duplicados — comprobable corriendo dos veces y
  comparando conteos.
- **Bueno, porque:** las rectificaciones de la fuente (`rectificado=t`)
  se reflejan automáticamente en el warehouse en la corrida siguiente.
- **Malo, porque:** el merge depende de que la clave natural sea
  confiable; lo vigilamos con un test `unique` bloqueante sobre
  (idpozo, anio, mes) en silver.
- **Malo, porque:** acumular snapshots completos en bronze crece
  linealmente en S3. A centavos por GB-mes es aceptable; con una
  lifecycle policy se archiva si hiciera falta.

### Confirmación

Se verifica con: la configuración `incremental` + `unique_key` en los
modelos dbt de silver; un test de integración que materializa dos veces la
misma partición y asserta igualdad de conteos (idempotencia); y el
procedimiento de backfill documentado en el runbook del data engineer,
ejecutado sobre una fecha histórica durante la demo.
