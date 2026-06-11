# Metabase como plataforma de BI

## Contexto y Declaración del Problema

La adenda exige una **plataforma de BI accesible vía web en la cual
usuarios no técnicos puedan revisar los datos**, consultando el modelo
estrella del warehouse ([ADR-0014](0014-modelo-dimensional-estrella.md)).
Los administradores deben poder acceder vía web a métricas del servicio.

El consumidor objetivo es el rol de negocio definido en
[ADR-0018](0018-roles-del-equipo.md) (data analyst / usuario de BI): debe
poder armar y leer dashboards de producción por cuenca, empresa y período
**sin escribir SQL**.

## Factores de Decisión

- Usabilidad para no técnicos (explorar sin SQL).
- Peso operativo: debe convivir con API + Prometheus + Grafana + Dagster
  + Postgres en la infraestructura del equipo
  ([ADR-0003](0003-docker-compose-para-orquestacion.md)).
- Conector Postgres de primera clase.
- Open source / sin costo.
- Esfuerzo de puesta en marcha y administración.

## Opciones Consideradas

- **Opción A — Metabase.** BI open source, un solo contenedor, orientada
  a preguntas point-and-click.
- **Opción B — Apache Superset.** BI open source más potente (SQL Lab,
  gran variedad de charts), arquitectura multi-servicio.
- **Opción C — Redash.** Herramienta de queries y dashboards centrada en
  SQL.

## Resultado de la Decisión

**Opción elegida: A (Metabase).**

**Por qué:**

- **Un contenedor, listo en minutos:** Metabase es un único servicio Java
  que se agrega al compose y se conecta a Postgres con el conector más
  maduro que tiene. Superset (B) requiere webserver + worker + redis +
  metadata DB y configuración de seguridad/roles considerable — no entra
  cómodo en la EC2 junto a todo lo demás, y su potencia extra (SQL Lab)
  apunta justo al usuario que la adenda *no* prioriza.
- **Pensada para no técnicos:** el flujo de "pregunta" de Metabase
  (elegir tabla, filtrar, agrupar, graficar) no requiere SQL. Redash (C)
  es SQL-first: cada visualización nace de una query escrita a mano, lo
  que excluye al usuario objetivo; además su desarrollo open source
  perdió ritmo tras la adquisición.
- **El modelo estrella simple rinde acá:** una fact y cuatro dimensiones
  ([ADR-0014](0014-modelo-dimensional-estrella.md)) se exploran bien con
  el editor visual; la decisión SCD1 evita que un usuario duplique filas
  por accidente al joinear dimensiones versionadas.
- **Sin costo y open source**, como el resto del stack.

### Consecuencias

- **Bueno, porque:** cumple el MUST con el menor costo operativo posible;
  acceso web para admins y usuarios de negocio; dashboards de producción
  por cuenca/empresa/período en la demo.
- **Bueno, porque:** también puede graficar `audit.quality_results`
  ([ADR-0015](0015-calidad-de-datos-dbt-tests.md)) como tablero de
  calidad visible.
- **Malo, porque:** Metabase OSS no versiona dashboards como código (la
  serialización es feature enterprise). Mitigación: los dashboards clave
  se documentan en el runbook del usuario de BI y la metadata de Metabase
  se persiste en Postgres (no en el H2 embebido por defecto) con backup.
- **Malo, porque:** menos tipos de visualización y menos control fino de
  permisos que Superset; aceptable para 3 usuarios internos + demo.

### Confirmación

Se verifica con: el servicio `metabase` en `docker-compose.yml` con su
metadata en Postgres; la conexión al warehouse configurada; al menos un
dashboard de producción funcionando en la demo; e instrucciones de acceso
en el `README.md` (requisito no funcional).
