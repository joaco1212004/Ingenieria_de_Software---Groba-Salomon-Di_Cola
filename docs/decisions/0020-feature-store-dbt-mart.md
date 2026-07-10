# Feature mart en dbt/gold como feature store

## Contexto y Declaración del Problema

La Adenda 3 exige que **el procesamiento y generación de features quede
persistido en un feature store que será utilizado durante la inferencia**. Las
features del modelo de declino ([ADR-0022](0022-orquestacion-del-entrenamiento.md))
son la serie mensual de **tasa diaria** por pozo (`prod_pet / tef`, NULL cuando
`tef <= 0`) con filtros de cohorte (≥ 12 meses de historia, ≥ 6 con producción
positiva), derivadas de `gold.fct_produccion_pozo_mes`
([ADR-0014](0014-modelo-dimensional-estrella.md)).

Hay que decidir **dónde y cómo viven esas features** de modo que el training
(job de Dagster) y la inferencia (la API en cada request,
[ADR-0023](0023-estrategia-de-serving-online.md)) lean exactamente lo mismo.

## Factores de Decisión

- Cumplimiento del MUST: features persistidas y usadas en inferencia.
- **Consistencia train/serve**: el riesgo clásico de MLOps es que el serving
  recalcule features con otra lógica y divirja del training (training-serving
  skew).
- Latencia requerida por la inferencia: el pronóstico es **mensual** y la API
  tiene un KPI de p99 < 5 s — no hay requisito de milisegundos.
- Lineage y gobierno: las features deben ser trazables en DataHub
  ([ADR-0016](0016-gobierno-de-datos-datahub.md)) — pedido explícito del
  equipo de modelado ("feature store o por lo menos data lineage").
- Complejidad y dependencias nuevas a días de la entrega.
- Reuso del stack existente: dbt ([ADR-0011](0011-transformacion-dbt-capas-medallion.md)),
  warehouse Postgres ([ADR-0012](0012-warehouse-postgresql.md)), Dagster.

## Opciones Consideradas

- **Opción A — Feature mart en dbt/gold.** Un modelo dbt
  (`gold.fct_features_declino`) materializa las features como tabla del
  warehouse, orquestado como un asset más del grupo `ml` en Dagster. Training
  e inferencia consultan la misma tabla.
- **Opción B — Feast (offline Postgres, online Redis).** Feature store
  dedicado: feature views declaradas en un `feature_repo/`, offline store
  sobre el warehouse y online store en Redis para retrieval de baja latencia.
- **Opción C — Tabla Postgres ad-hoc.** Un script Python del pipeline escribe
  una tabla de features fuera de dbt, sin declaración ni tests.

## Resultado de la Decisión

**Opción elegida: A (feature mart en dbt/gold).**

**Por qué:**

- **Consistencia train/serve por construcción:** el training
  (`pipeline/assets/ml.py`) y la API (`api/feature_client.py`) leen **la misma
  tabla** `gold.fct_features_declino`. No existe un segundo camino de cálculo
  que pueda divergir — el skew queda estructuralmente imposible.
- **Las features son SQL determinista:** una división (`prod_pet / tef` con
  guarda de `tef <= 0`) y filtros de cohorte por agregación. Es exactamente el
  tipo de transformación para el que dbt ya es la herramienta del stack
  ([ADR-0011](0011-transformacion-dbt-capas-medallion.md)): versionada,
  testeada (`schema.yml`) y documentada.
- **Lineage y gobierno gratis:** al ser un modelo dbt referenciado con
  `ref()`, el linaje `fct_produccion_pozo_mes → fct_features_declino` aparece
  en DataHub con la ingestión existente y en la UI de Dagster — cumple el
  pedido de trazabilidad del equipo de modelado sin código nuevo.
- **La latencia de Postgres alcanza y sobra:** la inferencia lee la historia
  mensual de UN pozo (cientos de filas indexadas) por request; un online store
  de milisegundos no aporta nada a un KPI de p99 < 5 s sobre datos mensuales.
- **Cero dependencias nuevas:** no se suma Redis ni el framework de Feast (y
  sus conflictos de resolución con Dagster/dbt en el mismo lockfile de
  Poetry), críticos de evitar a días de la entrega.

**Contra las alternativas:** Feast (B) es el feature store canónico, pero su
valor —online store de baja latencia, point-in-time joins entre decenas de
feature views, servir el mismo store a muchos equipos— no aplica a un caso con
una sola feature view mensual y un solo consumidor; a cambio cobra un
`feature_repo/` que mantener, Redis que operar en instancias ya justas de RAM
y dependencias pesadas en el lockfile. La tabla ad-hoc (C) parece más simple
pero pierde todo lo que dbt da gratis: tests de datos, documentación, lineage
en DataHub y el rebuild idempotente orquestado — es la opción A sin sus
beneficios.

### Consecuencias

- **Bueno, porque:** el NFR se cumple con una tabla gobernada: features
  persistidas en gold, consumidas por training e inferencia, con tests,
  lineage y rebuild idempotente por partición.
- **Bueno, porque:** agregar features nuevas (lags, medias móviles,
  categóricas de `dim_pozo`) es agregar columnas a un modelo dbt con su
  `schema.yml` — un PR revisable, sin tocar infraestructura.
- **Malo, porque:** no hay online store de milisegundos: si a futuro el
  producto exigiera inferencia de alta frecuencia o features en tiempo real,
  habría que revisitar (Feast puede montarse *encima* de este mismo mart como
  offline store, así que el camino de migración queda abierto).
- **Malo, porque:** no hay point-in-time correctness automática entre
  múltiples feature views; hoy no aplica (una sola vista, grano mensual), pero
  es el límite de la solución si el feature set crece en complejidad temporal.

### Confirmación

Se verifica con: el modelo `dbt/models/marts/ml/fct_features_declino.sql` con
su `schema.yml` en el repo, materializado por el grupo `ml` de Dagster; el
training leyéndolo en `pipeline/assets/ml.py` (`FEATURES_QUERY`) y la API en
`api/feature_client.py` (misma tabla); y el lineage
`fct_produccion_pozo_mes → fct_features_declino` visible en DataHub y en la UI
de Dagster.
