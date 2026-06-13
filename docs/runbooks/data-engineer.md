# Runbook: Data engineer - reprocesar Bronze por fecha

## Propósito y disparador

Este runbook explica cómo reprocesar una partición diaria de la capa Bronze cuando hay una rectificación de datos.gob.ar, un incidente de extracción, un objeto faltante en S3 o un pedido de backfill histórico. El procedimiento afecta a los assets `listado_pozos_bronze` y `produccion_no_convencional_bronze`, definidos en `pipeline/assets/bronze.py` y orquestados por Dagster en `bronze_daily_job`.

El disparador normal es el schedule `bronze_daily_schedule`, que corre todos los días a las 06:00, hora de Argentina. El disparador manual es un pedido puntual para reprocesar una fecha con formato `YYYY-MM-DD`.

## Rol, dueño y prerrequisitos

El dueño del procedimiento es el data engineer de guardia del equipo. Necesita acceso SSH a la EC2, permiso para ver Dagster UI, acceso de lectura al bucket `bronze-data-lake-energia` y permiso para ejecutar Docker Compose en el host.

Prerrequisitos:

- La EC2 debe tener asociado el IAM Role `EC2BronzeS3Role`.
- Los servicios `predictiva-dagster-code-server`, `predictiva-dagster-webserver` y `predictiva-dagster-daemon` deben estar levantados.
- El bucket Bronze debe existir.
- La fecha a reprocesar debe estar dentro del rango de particiones de Dagster.

## Pasos

1. Conectarse a la EC2:

   ```bash
   ssh -i ~/.ssh/Ingenieria_de_Software---Groba-Salomon-Di_Cola/Key-Group.pem ubuntu@api-hidraulicos-tipazos.duckdns.org
   ```

2. Entrar al repositorio:

   ```bash
   cd ~/Ingenieria_de_Software---Groba-Salomon-Di_Cola
   ```

3. Chequear que Dagster esté corriendo:

   ```bash
   docker ps --filter name=predictiva-dagster
   docker exec predictiva-dagster-daemon dagster schedule list -w workspace.yaml
   ```

4. Validar que la EC2 esté usando el IAM Role y no credenciales vencidas:

   ```bash
   docker exec predictiva-dagster-code-server python - <<'PY'
   import boto3
   print(boto3.client("sts").get_caller_identity()["Arn"])
   PY
   ```

5. Lanzar el backfill de la fecha solicitada:

   ```bash
   bash scripts/materialize-bronze.sh 2026-06-12
   ```

6. Abrir Dagster UI y revisar el run:

   ```text
   http://api-hidraulicos-tipazos.duckdns.org:3001
   ```

7. Confirmar que la partición existe en S3:

   ```bash
   docker exec predictiva-dagster-code-server python - <<'PY'
   import os
   import boto3

   bucket = os.environ["BRONZE_BUCKET"]
   s3 = boto3.client("s3")
   for dataset in ["listado_pozos", "produccion_no_convencional"]:
       prefix = f"datalake/bronze/{dataset}/fecha_extraccion=2026-06-12/"
       response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
       print(prefix, response.get("KeyCount", 0))
   PY
   ```

## Validación

El reproceso salió bien si:

- El run `bronze_daily_job` termina en `SUCCESS`.
- Dagster muestra materializaciones para los dos assets Bronze.
- Existen exactamente los objetos esperados:
  - `datalake/bronze/listado_pozos/fecha_extraccion=YYYY-MM-DD/listado_pozos.csv`
  - `datalake/bronze/produccion_no_convencional/fecha_extraccion=YYYY-MM-DD/produccion_no_convencional.csv`
- Los tamaños de los objetos son mayores a cero y consistentes con los últimos snapshots.
- El schedule `bronze_daily_schedule` queda en estado `RUNNING`.

## Si algo falla

Si falla por `ExpiredToken`, la EC2 no está usando el IAM Role o el contenedor todavía tiene variables AWS viejas. Hay que validar el role con STS, limpiar credenciales manuales del `.env` y recrear Dagster:

```bash
docker-compose stop dagster-daemon dagster-webserver dagster-code-server
docker rm -f predictiva-dagster-daemon predictiva-dagster-webserver predictiva-dagster-code-server
docker-compose up -d dagster-code-server dagster-webserver dagster-daemon
```

Si falla la descarga desde datos.gob.ar, conviene esperar unos minutos y reintentar. El asset ya tiene retries con backoff, pero una caída prolongada de la fuente se escala al equipo como incidente de frescura.

Si falla S3 por permisos, revisar la policy asociada a `EC2BronzeS3Role`. El plan B es no borrar objetos existentes y dejar la partición anterior como última versión confiable hasta corregir permisos.

Si la EC2 queda sin memoria, revisar swap y estado del host:

```bash
free -m
swapon --show
docker ps
```

## Consideraciones no funcionales

Frescura: Bronze debe actualizarse una vez por día. Para el alcance del TP, una frescura menor o igual a 24 horas es suficiente porque las fuentes oficiales no son datos operacionales minuto a minuto.

Costo: no se levanta otra EC2 para reprocesar Bronze. El backfill usa la instancia actual, S3 y Dagster ya desplegados. Si hay que reprocesar muchas fechas, se hace por ventanas acotadas para no saturar CPU, memoria ni transferencia.

Seguridad: la EC2 usa IAM Role y no access keys persistidas. No se deben commitear `.env`, `.pem` ni tokens. Los CSV públicos no contienen PII sensible, pero el bucket sigue siendo un activo del proyecto y debe mantenerse con acceso restringido.

Calidad operativa: un backfill fallido bloquea la promoción de esa fecha hacia Silver/Gold. No se deben publicar métricas de negocio sobre una partición Bronze incompleta.

## Decisión funcional justificada

Decisión: Bronze guarda snapshots completos de ambas fuentes para cada `fecha_extraccion`, sin transformar columnas ni filtrar registros.

Desde la perspectiva del data engineer, esta decisión reduce ambigüedad operativa. Ante una rectificación de datos.gob.ar, el equipo puede demostrar qué archivo crudo recibió el sistema en una fecha concreta y puede reprocesar aguas abajo sin discutir si una transformación temprana alteró el dato. También simplifica el soporte: si un analista cuestiona una métrica, el data engineer puede comparar el objeto Bronze exacto contra la fuente oficial y separar problemas de extracción de problemas de transformación.

## Decisión no funcional justificada

Decisión: el pipeline Bronze corre una vez por día a las 06:00, hora de Argentina, y los backfills manuales se ejecutan solo ante pedido o incidente.

Desde la perspectiva del data engineer, esta frecuencia equilibra frescura y costo. Correr varias veces por día no aporta valor proporcional porque las fuentes no son datos de streaming, pero sí aumenta logs, consumo de CPU, uso de red y riesgo de saturar una EC2 chica. La corrida temprana deja los datos listos para que analytics y BI trabajen durante el día, manteniendo el gasto bajo y la operación predecible.
