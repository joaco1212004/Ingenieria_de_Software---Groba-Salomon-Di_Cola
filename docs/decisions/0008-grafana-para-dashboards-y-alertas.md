# Grafana para dashboards y alertas

## Contexto y Declaración del Problema

La adenda técnica exige un *dashboard de monitoreo* que muestre métricas de
aplicación (latencia, disponibilidad, frecuencia de consulta) y de
infraestructura (CPU, memoria, disco), con **alertas automáticas** ante
fallas de servicio, incumplimiento de latencia o alta tasa de error.

En los ADRs [0006](0006-prometheus-para-metricas-de-la-api.md) y
[0007](0007-node-exporter-para-metricas-de-computo.md) elegimos Prometheus
+ Node Exporter como pipeline de métricas. Falta decidir la herramienta de
visualización y de gestión de alertas.

## Factores de Decisión

- Datasource compatible con la pipeline ya elegida (Prometheus).
- Versionado de los dashboards como código.
- Costo monetario sobre los créditos de AWS Academy.
- Soporte nativo para alertas con integración a notificaciones (email,
  Slack, etc.).
- Simplicidad operativa (corre en la misma EC2 vía Docker Compose).

## Opciones Consideradas

- **Opción A — Grafana self-hosted en Docker Compose.** Imagen oficial
  `grafana/grafana` como servicio del compose, con datasource Prometheus
  preconfigurado y dashboards versionados como JSON en el repo.
- **Opción B — Amazon CloudWatch Dashboards.** Dashboards definidos
  directamente en la consola de AWS, consumiendo métricas que la app
  publique a CloudWatch.
- **Opción C — Amazon Managed Grafana.** Grafana como servicio gestionado
  por AWS, con datasources hacia Prometheus y CloudWatch.

## Resultado de la Decisión

**Opción elegida: A (Grafana self-hosted en Docker Compose).**

**Por qué:**

- **Datasource nativo de Prometheus:** Grafana fue diseñado en torno al
  ecosistema Prometheus. PromQL como lenguaje de query, autocompletado de
  labels en el editor de paneles y plantillas pre-armadas en
  grafana.com/dashboards (incluyendo dashboards canónicos de Node
  Exporter) reducen el tiempo a primer dashboard útil a minutos.
  CloudWatch Dashboards no consume métricas Prometheus; Managed Grafana sí
  pero por un costo (USD 9 por usuario activo / mes en el plan estándar).
- **Dashboards como código:** Grafana permite exportar cada dashboard a
  JSON y provisionarlos automáticamente con el archivo
  `provisioning/dashboards/*.yaml`. Esos JSON viven en el repo
  (`infra/grafana/dashboards/`), se revisan en pull requests y se
  redespliegan con cada `docker compose up`. CloudWatch Dashboards viven
  en la consola de AWS y son engorrosos de versionar (existe la API pero
  el flujo de edición habitual es por GUI).
- **Alertas integradas:** Grafana 9+ trae el motor de alertas unificado
  (Grafana Alerting). Definimos reglas como código en el mismo repo
  (`provisioning/alerting/*.yaml`) y permite **EN FUTURO DESARROLLO** notificar las alertas por email y/o Slack vía
  contact points. Cubre el requisito de la adenda sin sumar herramientas
  adicionales (Alertmanager queda como opción futura si necesitamos
  enrutamiento más sofisticado).
- **Costo cero en créditos AWS:** el contenedor corre en la misma t2.micro
  con un overhead modesto (~50 MB RAM en idle). Managed Grafana cobra por
  usuario; CloudWatch cobra por dashboard activo y por alarma.
- **Coherencia de stack:** API + Prometheus + Node Exporter + Grafana es
  el stack de observabilidad open-source más estandarizado de la
  industria. Cualquier persona que se sume al equipo lo reconoce.

### Consecuencias

- **Bueno, porque:** los dashboards y alertas son artefactos versionados;
  el stack completo (API + Prometheus + Node Exporter + Grafana) levanta
  con un único `docker compose up`; portabilidad total fuera de AWS si en
  una fase futura migramos.
- **Malo, porque:** Grafana corre en la misma t2.micro que monitoree. Si
  la VM cae, perdemos el dashboard junto con el sistema observado. Las
  alertas que disparen en ese momento no se entregan. Mitigación parcial
  futura: usar CloudWatch como red de seguridad para alertas
  específicas de "instancia caída".
- **Malo, porque:** la persistencia de Grafana (usuarios, anotaciones,
  cambios manuales hechos en la GUI) depende del volumen del contenedor.
  Forzamos el modelo "todo viene del repo" para que la pérdida del
  volumen no sea catastrófica: si se cae, redeployamos y los dashboards
  vuelven solos desde provisioning.
- **No exploramos** Amazon Managed Grafana: la única ventaja real
  (gestión por AWS) no compensa el costo por usuario en un equipo de
  tres personas que ya está cómodo administrando un contenedor más en
  Compose.

### Confirmación

Se verifica con la presencia del servicio `grafana` en
`docker-compose.yml`, los archivos JSON de dashboards en
`infra/grafana/dashboards/` y los archivos YAML de provisioning de
datasources y alertas en `infra/grafana/provisioning/`. Durante la demo
de Fase 1 se muestran los paneles de latencia, uptime y uso de recursos,
y se gatilla manualmente al menos una alerta de ejemplo.