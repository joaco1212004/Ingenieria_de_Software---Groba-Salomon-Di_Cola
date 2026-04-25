# Node Exporter para métricas de recursos de cómputo

## Contexto y Declaración del Problema

La agenda técnica exige monitorear el **uso de recursos** del Motor de
Modelado y del Servidor API: CPU, memoria, I/O de disco. Estas métricas son
a nivel **host**, no aplicación: las emite el sistema operativo, no el
proceso de FastAPI.

En el [ADR-0006](0006-prometheus-para-metricas-de-la-api.md) elegimos
Prometheus como time-series database para las métricas de aplicación.
Necesitamos un **agente que exponga las métricas del host** en un formato
compatible con Prometheus (modelo pull, endpoint `/metrics`) o, en su
defecto, integrarnos con CloudWatch Agent que publica las mismas métricas
hacia CloudWatch.

## Factores de Decisión

- Coherencia con la decisión ya tomada para métricas de aplicación
  (Prometheus, ADR-0006).
- Costo de mantener una segunda pipeline de métricas paralela hacia
  CloudWatch.
- Esfuerzo de configuración inicial.
- Consumo de recursos sobre la t2.micro (que ya hospeda API + Prometheus
  + Grafana).

## Opciones Consideradas

- **Opción A — Node Exporter como contenedor en Docker Compose.** El
  exporter corre como servicio adicional del compose, con acceso a `/proc`
  y `/sys` del host vía bind mounts, y expone `/metrics` para que
  Prometheus lo scrapee.
- **Opción B — CloudWatch Agent en la EC2.** El agent corre como demonio
  en el host, lee métricas del SO y las publica como custom metrics en
  CloudWatch.
- **Opción C — cAdvisor (en lugar de Node Exporter).** Reporta métricas a
  nivel **contenedor** en lugar de a nivel host.

## Resultado de la Decisión

**Opción elegida: A (Node Exporter en Docker Compose).**

**Por qué:**

- **Una sola pipeline de métricas:** Node Exporter habla el mismo
  protocolo que `prometheus-client` (texto plano vía HTTP, modelo pull).
  El mismo Prometheus scrapea los dos targets; el mismo Grafana consulta
  los dos en el mismo datasource. CloudWatch Agent obligaría a mantener
  **dos pipelines en paralelo** (Prometheus para app + CloudWatch para
  host), con dos datasources distintos en el dashboard y dos lenguajes de
  query — sobre-ingeniería para Fase 1.
- **Configuración trivial:** Node Exporter es una imagen oficial
  (`prom/node-exporter`) con flags estándar para montar `/proc`, `/sys` y
  `/`. Tres líneas en el compose. CloudWatch Agent requiere instalación
  en el host, archivo de configuración JSON, IAM role asociado a la EC2
  con permisos de PutMetricData, y debug específico cuando algo falla.
- **Costo cero en créditos AWS Academy:** corre dentro de la misma EC2
  como contenedor minimalista (~10 MB en RAM). CloudWatch custom metrics
  cobra por métrica × dimensión × mes; con CPU + memoria + disco en
  varias dimensiones se suma rápido.
- **Cobertura adecuada:** Node Exporter expone CPU (por core), memoria
  (free, used, cached, swap), disco (I/O, espacio), red (bytes
  in/out/error), load average y filesystem. Cubre exactamente la lista de
  la agenda. cAdvisor sería complementario (métricas por contenedor) pero
  agrega un servicio más sobre la t2.micro sin valor inmediato para la
  demo; lo dejamos para una fase futura si hace falta debugear consumo
  por servicio.

### Consecuencias

- **Bueno, porque:** unifica la observabilidad en un único stack; los
  dashboards de Grafana mezclan métricas de app y de host con la misma
  query language (PromQL); reproducible en local con un `docker compose
  up`.
- **Malo, porque:** corre en la misma máquina que mide. Si la t2.micro
  cae, dejamos de ver tanto los síntomas (latencia alta) como las causas
  (CPU saturada). Es la misma limitación del ADR-0006 y se acepta como
  trade-off de Fase 1.
- **Malo, porque:** Node Exporter dentro de un contenedor mide el host
  (gracias a los bind mounts), no el contenedor. Para métricas
  por-contenedor habría que sumar cAdvisor; lo postergamos.
- **No descartamos CloudWatch Agent permanentemente:** si en una fase
  futura se exige integración con alarmas nativas de AWS (p. ej. Auto
  Scaling, SNS para notificaciones operativas), revisar este ADR.

### Confirmación

Se verifica con la presencia del servicio `node-exporter` en
`docker-compose.yml`, los bind mounts hacia `/proc`, `/sys` y `/` del
host, y dashboards en Grafana que muestran métricas de CPU/memoria/disco
del host durante la demo.