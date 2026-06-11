# Bucket S3 como datalake para la capa bronze

## Contexto y Declaración del Problema

La arquitectura medallion exigida por la Adenda 2 arranca en una **capa
bronze**: los datos crudos, tal cual salen de la fuente, sin transformar.
Nuestras fuentes son dos CSVs de datos.gob.ar (producción de pozos por
período y listado de pozos), que se republican completos periódicamente y
pesan cientos de MB (300k–400k filas cada uno y creciendo).

Necesitamos decidir **dónde aterriza la extracción**: un almacenamiento
durable, barato, particionable por fecha de extracción (para auditar
snapshots y habilitar el reprocesamiento exigido), y accesible tanto desde
el orquestador ([ADR-0009](0009-orquestador-dagster.md)) en producción
como desde el entorno local y el CI sin fricción.

## Factores de Decisión

- Durabilidad e inmutabilidad: bronze es la fuente de verdad cruda; si se
  pierde, no hay re-derivación posible de snapshots históricos.
- Costo sobre los créditos de AWS Academy y sobre el disco de la EC2.
- Desarrollo local y CI **sin credenciales AWS** (mismo criterio que el
  [ADR-0006](0006-prometheus-para-metricas-de-la-api.md)).
- Desacople almacenamiento/cómputo: la EC2 puede recrearse sin perder
  datos.
- Layout particionable alineado con las particiones de Dagster, para que
  reprocesar una fecha sea sobrescribir una partición (idempotencia).

## Opciones Consideradas

- **Opción A — Bucket S3** con layout particionado
  `s3://<bucket>/datalake/bronze/<dataset>/fecha_extraccion=YYYY-MM-DD/`.
- **Opción B — Filesystem local de la EC2 (EBS).** Los CSVs se guardan en
  un directorio del host montado en los contenedores.
- **Opción C — MinIO self-hosted en la EC2.** Object storage
  S3-compatible administrado por nosotros en el compose.
- **Opción D — Tablas raw en PostgreSQL.** Cargar los CSVs crudos
  directamente como tablas en el warehouse.

## Resultado de la Decisión

**Opción elegida: A (bucket S3).**

**Por qué:**

- **Durabilidad sin operarla:** S3 ofrece 99.999999999% de durabilidad
  sin que administremos discos, réplicas ni backups. Con MinIO (C)
  seríamos nosotros los responsables de esa garantía sobre una sola EC2.
- **Desacopla el lake del cómputo:** si la instancia muere o se recrea
  (algo frecuente con AWS Academy), bronze sobrevive intacto. Con EBS
  local (B) los snapshots viven y mueren con la VM y compiten por su
  disco limitado.
- **Costo marginal:** almacenar algunos GB de CSV cuesta centavos por
  mes, muy por debajo de agrandar el EBS de la EC2.
- **Particiones = idempotencia y auditoría:** cada corrida de extracción
  escribe el snapshot completo bajo su partición
  `fecha_extraccion=YYYY-MM-DD/`. Reprocesar una fecha es sobrescribir esa
  partición (idempotente, exigido por la adenda) y el historial de
  snapshots queda auditable — clave porque la fuente rectifica datos
  retroactivamente (columna `rectificado`, ver
  [ADR-0013](0013-tipo-de-carga-incremental-merge.md)).
- **La API S3 es estándar de facto:** boto3/s3fs aceptan `endpoint_url`,
  así que **en CI y desarrollo local usamos MinIO como doble de S3** en
  Docker Compose, con el mismo código y sin credenciales AWS. Es decir:
  la opción C no se descarta, se relega al rol de S3 de mentira para
  tests; en producción no nos auto-administramos el storage.

**Contra la opción D:** cargar crudos en Postgres mezcla las capas
medallion (bronze deja de ser el archivo original byte a byte), infla el
warehouse con datos sin valor de consulta y pierde la inmutabilidad del
snapshot. El warehouse entra recién en silver/gold
([ADR-0012](0012-warehouse-postgresql.md)).

### Consecuencias

- **Bueno, porque:** bronze es inmutable, barato, durable y auditable;
  las particiones por fecha de extracción calzan 1:1 con las particiones
  de Dagster, haciendo trivial el backfill.
- **Bueno, porque:** el integration test del CI levanta MinIO en el
  compose y materializa el pipeline end-to-end sin tocar AWS, y los unit
  tests mockean S3 con `moto`.
- **Malo, porque:** producción depende de credenciales AWS en la EC2
  (las gestionamos como las demás secrets del deploy,
  [ADR-0005](0005-cd-con-github-actions-via-ssh-a-ec2.md)) y de la
  vigencia de los créditos de AWS Academy.
- **Malo, porque:** MinIO en CI no es S3 real: hay diferencias sutiles
  (IAM, consistencia de listados). Lo aceptamos porque la superficie que
  usamos (put/get/list por prefijo) es idéntica.
- **Malo, porque:** guardar el snapshot completo en cada extracción crece
  linealmente. A este volumen es despreciable; si escalara, una lifecycle
  policy de S3 archiva snapshots viejos a Glacier.

### Confirmación

Se verifica con: el bucket con el layout particionado descrito y al menos
dos snapshots de fechas distintas; el asset de extracción de Dagster
escribiendo en él; el servicio `minio` en el `docker-compose.yml` usado
por `scripts/integration-test.sh`; y un re-run de la misma partición que
no duplica datos.
