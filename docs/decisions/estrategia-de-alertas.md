# Estrategia de alertas

**status: Aceptado**
**date: 2026-04-13**
**decision-makers: Groba, Salomon, Di Cola**
**consulted:**
**informed: Equipo Docente (Ingeniería de Software)**

## Contexto y Declaración del Problema

La adenda técnica de Fase 1 exige que el dashboard de monitoreo dispare
alertas automáticas (por email o Slack) ante fallas de servicio,
incumplimiento de latencia o alta tasa de error de la API. Acordado en el
ADR 0002 que usaremos Prometheus + Grafana como herramienta principal de
observabilidad, debemos decidir **por dónde salen los avisos**: si usamos
Grafana Alerting con notificación SMTP (propia del stack que ya estamos
levantando) o Amazon CloudWatch Alarms + SNS (nativo del cloud donde corre
la instancia EC2).

La sutileza es que el sistema que monitorea a la aplicación se convierte él
mismo en un componente crítico: si el único emisor de alertas es el
contenedor Grafana y la instancia EC2 donde vive cae, **nadie notifica que
nadie está notificando**. Necesitamos una estrategia que evite ese punto
ciego sin complicar la operación diaria.

## Opciones Consideradas

- **Opción A — Sólo Grafana Alerting vía SMTP.** Configuramos el contenedor
  Grafana con variables `GF_SMTP_*` apuntando a un proveedor SMTP externo
  (ej. Gmail con App Password, Mailgun, Amazon SES). Grafana evalúa las
  reglas sobre las métricas de Prometheus y dispara emails cuando se superan
  los umbrales.
- **Opción B — Sólo CloudWatch Alarms + SNS.** Publicamos métricas custom a
  CloudWatch, definimos alarmas en la consola AWS, y usamos un SNS topic con
  suscripción por email para notificar al equipo. No requiere instrumentación
  adicional dentro del contenedor.
- **Opción C — Estrategia de capas: Grafana Alerting para alertas de
  negocio, CloudWatch/SNS como red de seguridad de infraestructura.**
  Grafana se encarga de las alertas que dependen de métricas de aplicación
  (latencia del endpoint de forecast, tasa de errores HTTP 5xx, frecuencia
  de consulta anómala). En paralelo, configuramos alarmas básicas de
  CloudWatch sobre métricas nativas de EC2 (StatusCheckFailed, CPUUtilization
  crítica) con notificación SNS → email, para que la infraestructura siga
  avisando aunque todo el stack de Docker Compose esté caído.

## Resultado de la Decisión

**Opción elegida: C (estrategia de capas).**

**Por qué:**

- Resuelve el riesgo de **alerta circular**. Si usáramos únicamente Grafana
  Alerting (Opción A), un kernel panic en la EC2, un OOM kill o un `docker
  compose down` accidental dejarían la API fuera de servicio **y**
  silenciarían exactamente el componente que debería avisarlo. CloudWatch
  corre fuera de la instancia, por lo cual sigue viendo a EC2 aunque Grafana
  esté muerto.
- Grafana Alerting es el lugar natural para expresar reglas sobre métricas
  de aplicación, porque tiene acceso directo a las series de Prometheus
  (latencia percentil 95 del endpoint, tasa de errores por código HTTP,
  contadores por endpoint). Definirlas en CloudWatch implicaría exportar
  todas esas métricas a CloudWatch con una granularidad que no necesitamos.
- CloudWatch/SNS cubre la capa de **infraestructura** sin que tengamos que
  escribir código: las métricas `StatusCheckFailed_Instance`,
  `StatusCheckFailed_System` y `CPUUtilization` ya existen por el solo hecho
  de tener la instancia corriendo, y configurar un SNS topic con
  suscripción por email toma cinco minutos en la consola AWS Academy.
- Mantiene la separación limpia de responsabilidades: el equipo de
  desarrollo mira Grafana para entender el comportamiento del servicio, el
  oncall mira su mail para enterarse de que "algo grande está mal" incluso
  cuando no puede abrir Grafana.

### Consecuencias

- **Bueno, porque:** no dependemos de un único punto de notificación; las
  reglas de negocio viven en Grafana, donde son versionables (JSON del
  dashboard y archivos de provisioning); las alertas de infra usan
  herramientas gestionadas que no nos cuestan trabajo operativo; y la
  configuración SMTP queda como variables de entorno del servicio `grafana`
  en `docker-compose.yml`, sin credenciales hardcodeadas.
- **Malo, porque:** tenemos dos lugares donde configurar alertas, y es
  posible que una misma caída genere notificaciones duplicadas (Grafana
  avisa "tasa de error alta" y CloudWatch avisa "StatusCheck falló"). Lo
  aceptamos: en Fase 1 preferimos ruido a silencio.
- **Requisito operativo:** el SMTP relay que use Grafana debe estar
  documentado (qué proveedor, qué usuario, dónde vive la App Password) para
  que cualquier miembro del equipo pueda rotarlo sin acceder al estado
  interno del contenedor. Las credenciales se inyectan desde secrets de
  GitHub Actions al momento del deploy.
