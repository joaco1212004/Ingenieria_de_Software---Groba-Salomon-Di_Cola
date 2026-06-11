# Roles del equipo: data engineer, analytics engineer y data analyst

## Contexto y Declaración del Problema

La adenda exige elegir **al menos 2 roles** de los vistos en clase — al
menos uno cercano al negocio (data PM, data analyst, data owner, usuario
de BI) y al menos uno cercano a la implementación (data engineer,
analytics engineer, data steward) — y escribir un **runbook por rol** en
`docs/runbooks/` con un procedimiento concreto y propio de este proyecto.

Somos un equipo de 3 personas. La decisión es **qué combinación de roles
adoptar** y qué responsabilidades concretas tiene cada rol **dentro de
este repositorio**, de modo que los runbooks salgan de procedimientos
reales y no genéricos.

## Factores de Decisión

- Cumplir el MUST: ≥2 roles, ≥1 de negocio y ≥1 de implementación.
- Que cada rol mapee 1:1 con artefactos que el repo realmente tiene
  (assets de Dagster, modelos dbt, dashboards Metabase, catálogo
  DataHub) — si no, el runbook sale genérico y la adenda lo penaliza.
- Que los 3 integrantes tengan un rol con carga comparable.
- Que el ownership ordene la revisión de PRs (los devs DEBEN recibir
  feedback de tests en PRs — requisito de la adenda).

## Opciones Consideradas

- **Opción A — Data engineer + analytics engineer + data analyst.**
  Tres roles, uno por integrante: dos de implementación, uno de negocio.
- **Opción B — Data engineer + data PM.** Implementación + negocio vía
  gestión de producto de datos.
- **Opción C — Data steward + data owner.** Par centrado en gobernanza.
- **Opción D — Analytics engineer + usuario de BI.** Par mínimo centrado
  en el warehouse y su consumo.

## Resultado de la Decisión

**Opción elegida: A (data engineer + analytics engineer + data
analyst).**

**Por qué:**

- **Cada rol ownea artefactos que existen en el repo**, así los runbooks
  describen procedimientos reales y ejecutables de punta a punta (lo que
  exige la adenda), no descripciones de manual:
  - el data engineer ownea la extracción y el backfill —procedimientos
    que existen porque existen las particiones de Dagster
    ([ADR-0009](0009-orquestador-dagster.md),
    [ADR-0013](0013-tipo-de-carga-incremental-merge.md));
  - el analytics engineer ownea modelos y tests dbt
    ([ADR-0011](0011-transformacion-dbt-capas-medallion.md),
    [ADR-0015](0015-calidad-de-datos-dbt-tests.md));
  - el data analyst ownea dashboards y glosario
    ([ADR-0017](0017-bi-metabase.md),
    [ADR-0016](0016-gobierno-de-datos-datahub.md)).
- **Un rol por integrante:** B y D dejan a una persona sin rol definido o
  a dos compartiendo uno, diluyendo el ownership.
- **Contra B (data PM):** sin stakeholders externos reales, la "gestión
  de producto de datos" en un equipo de 3 queda declarativa: el runbook
  resultante sería genérico — exactamente lo que la adenda invalida.
- **Contra C (steward + owner):** son roles de gobernanza sobre masa de
  datos/usuarios que este proyecto no tiene; además no cubren bien el
  lado de implementación del MUST.

### Responsabilidades dentro del repositorio

| Rol (perfil) | Ownea en el repo | Revisa en PRs | Runbook |
|---|---|---|---|
| **Data engineer** (implementación) | Assets de extracción/carga de Dagster, layout de bronze en S3, `docker-compose.yml` de datos, CI del pipeline | Cambios en extracción, particiones, infra de datos | `docs/runbooks/data-engineer.md`: **ejecutar un backfill / reprocesar una fecha** tras una rectificación de la fuente |
| **Analytics engineer** (implementación) | Proyecto dbt (`staging/`, `marts/`), tests de calidad, docs del modelo | Cambios en modelos dbt, tests, esquema del estrella | `docs/runbooks/analytics-engineer.md`: **agregar una métrica/columna a gold** con sus tests y docs, de PR a producción |
| **Data analyst** (negocio) | Dashboards de Metabase, glosario y descripciones en DataHub | Que los cambios de gold no rompan dashboards; definiciones de métricas | `docs/runbooks/data-analyst.md`: **construir y validar un dashboard** sobre el estrella, incluyendo el chequeo de frescura/calidad antes de publicar |

Cada runbook debe incluir las secciones exigidas por la adenda
(propósito/disparador, dueño/prerrequisitos, pasos, validación, plan de
falla, consideraciones no funcionales) y justificar **una decisión
funcional y una no funcional** desde los incentivos del rol.

La asignación rol ↔ integrante se registra al crear los runbooks; los
roles pueden rotar entre integrantes documentándolo en este ADR.

### Consecuencias

- **Bueno, porque:** los runbooks quedan pre-definidos con procedimientos
  reales del repo; el ownership de PRs queda explícito y alineado con el
  requisito de feedback de tests en PRs.
- **Bueno, porque:** cubre de sobra el MUST (3 roles: 2 implementación +
  1 negocio).
- **Malo, porque:** en un equipo de 3 todos tocan todo en la práctica;
  los roles son sombreros, no silos — el riesgo es que el ownership quede
  en papel. Mitigación: el ownership se ejerce en la revisión de PRs, que
  sí queda registrada en GitHub.

### Confirmación

Se verifica con: los tres runbooks creados en `docs/runbooks/` con las
secciones exigidas; PRs del repo revisados según la tabla de ownership; y
la asignación de integrantes registrada.
