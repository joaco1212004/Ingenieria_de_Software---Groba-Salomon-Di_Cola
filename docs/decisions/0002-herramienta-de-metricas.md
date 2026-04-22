# Herramienta de métricas y visualización

**status: Aceptado**
**date: 2026-04-13**
**decision-makers: Groba, Salomon, Di Cola**
**consulted:**
**informed: Equipo Docente (Ingeniería de Software)**

## Contexto y Declaración del Problema

La adenda técnica de la Fase 1 exige un dashboard de monitoreo que cubra tanto
métricas de desempeño del sistema (latencia de pronóstico, disponibilidad de la
API, uso de recursos) como métricas de negocio/adopción (frecuencia de consulta
de la API REST). El equipo desplegó la API sobre una instancia EC2 dentro de
AWS Academy, con lo cual tenemos dos caminos naturales para instrumentar y
visualizar estas métricas: el stack open-source **Prometheus + Grafana** (que
corre dentro del mismo host vía Docker Compose) o el servicio gestionado
**Amazon CloudWatch** (Metrics + Logs + Dashboards).

Necesitamos elegir qué combinación de herramientas usar para cumplir con los
KPIs definidos en la adenda (latencia < 5s, uptime 99.5%, frecuencia de
consulta por endpoint) sin generar duplicación de paneles ni sobre-ingeniería
para una Fase 1 que es esencialmente un mock.

## Opciones Consideradas

- **Opción A — Prometheus + Grafana self-hosted (en Docker Compose).**
  Instrumentamos FastAPI con `prometheus-client`, exponemos `/metrics`, y
  montamos Prometheus y Grafana como servicios adicionales en el mismo
  `docker-compose.yml` que corre en EC2.
- **Opción B — Amazon CloudWatch nativo.** Publicamos métricas custom desde la
  aplicación con el SDK de AWS (boto3) y construimos los dashboards
  directamente en la consola de CloudWatch. Las métricas de infraestructura
  (CPU, memoria, red) vienen gratis del agente de CloudWatch.
- **Opción C — Híbrido: Grafana como pane-of-glass, con datasources hacia
  CloudWatch y Prometheus.** Grafana soporta nativamente CloudWatch como
  datasource, por lo cual los dashboards pueden consumir métricas de infra
  desde CloudWatch y métricas de aplicación desde Prometheus sin duplicar
  paneles.

## Resultado de la Decisión

**Opción elegida: A (Prometheus + Grafana), con la puerta abierta a evolucionar
hacia C si en fases posteriores necesitamos consolidar métricas de infra AWS.**

**Por qué:**

- La instrumentación de FastAPI con `prometheus-client` es extremadamente barata
  (una dependencia de Poetry, una función de middleware) y el endpoint
  `/metrics` no necesita credenciales AWS ni red saliente, lo cual simplifica
  el desarrollo local y los tests de integración.
- Grafana nos da dashboards versionables como JSON dentro del repo
  (`infra/grafana/dashboards/`), lo cual encaja con nuestra filosofía de
  infra-as-code y es fácil de revisar en pull requests. CloudWatch dashboards,
  en cambio, viven en la consola de AWS y son más engorrosos de versionar.
- CloudWatch cubre muy bien métricas de **infraestructura** AWS (CPU de la
  instancia, estado del EBS, tráfico de red) sin necesidad de instrumentación
  extra, y Grafana puede usarlo como datasource. Esto deja la puerta abierta a
  la Opción C en fases futuras: si en algún momento necesitamos mirar métricas
  de infra sin duplicar esfuerzo, agregamos el datasource en Grafana y
  reutilizamos los paneles.
- Para Fase 1, sobre una única instancia EC2 con un mock, montar todo el
  stack de CloudWatch custom metrics es sobre-ingeniería: paga costos
  marginales por métrica publicada y nos ata al vendor para algo que por
  definición es desechable.

### Consecuencias

- **Bueno, porque:** los dashboards y la configuración de scraping son
  artefactos de texto versionables; la instrumentación es agnóstica al
  proveedor cloud, por lo cual una futura migración a EKS, Fargate o incluso
  otro cloud no requiere reescribir las métricas de aplicación; el stack corre
  también en local vía `docker compose up`, eliminando la diferencia entre
  desarrollo y producción para observabilidad.
- **Malo, porque:** corremos Prometheus y Grafana en la misma instancia EC2
  t2.micro que la API, lo cual agrega carga de memoria/CPU y nos expone al
  riesgo de que si la instancia cae, perdemos también la herramienta de
  monitoreo. Este riesgo se mitiga parcialmente en el ADR 0003 con
  CloudWatch/SNS como red de seguridad para alertas de infraestructura.
- **Trade-off conocido:** elegimos simplicidad operativa (un único `docker
  compose up`) a costa de no aprovechar integraciones nativas de CloudWatch
  (por ejemplo, alarmas que disparan Auto Scaling). Si el producto escalara
  fuera de una única instancia, reconsideraríamos hacia la Opción C.
