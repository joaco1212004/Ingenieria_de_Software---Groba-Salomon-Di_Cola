# Reuso de Dagster para orquestar el entrenamiento del modelo

## Contexto y Declaración del Problema

La Adenda 3 exige que **el entrenamiento y despliegue de modelos se realice de
manera recurrente y automática**, y que exista orquestación que **permita
repetir el entrenamiento para un día dado**. El flujo de ML a orquestar es:
construir features → entrenar → validar (gate de métricas) → registrar/promover
en MLflow ([ADR-0019](0019-experiment-tracking-y-model-registry-mlflow.md)).

La plataforma de datos ya corre sobre Dagster
([ADR-0009](0009-orquestador-dagster.md)) con particiones diarias por
`fecha_extraccion` y las transformaciones dbt como assets
([ADR-0011](0011-transformacion-dbt-capas-medallion.md)). La decisión es si el
pipeline de ML reusa ese orquestador o incorpora uno propio.

## Factores de Decisión

- Cumplimiento de los MUST: retrain recurrente/automático, repetible para un
  día dado (idempotencia), con trigger de reentrenamiento.
- Dependencia explícita del entrenamiento sobre los datos gold: el retrain
  debe dispararse cuando cambian los datos de `fct_produccion_pozo_mes`.
- Reuso del orquestador ya en producción vs sumar y mantener uno nuevo.
- Naturaleza del cómputo: el modelo es CPU-bound (curva de declino de Arps +
  gradient boosting sobre residuos), no requiere GPUs ni entrenamiento
  distribuido.
- Footprint: corre sobre las EC2 del equipo con Docker Compose.
- Testeabilidad en el CI existente ([ADR-0004](0004-ci-con-github-actions.md)).

## Opciones Consideradas

- **Opción A — Reusar Dagster.** Un nuevo grupo de assets `ml`
  (`build_features → train → validate → register`) con su `ml_training_job` y
  un `@schedule`, dentro del mismo despliegue de Dagster que la plataforma de
  datos.
- **Opción B — Apache Airflow.** Orquestador dedicado para el pipeline de ML,
  separado del de datos.
- **Opción C — Kubeflow Pipelines / Metaflow.** Orquestadores ML-native sobre
  Kubernetes, pensados para pipelines de ML a escala.
- **Opción D — cron + scripts.** Un `train.py` disparado por crontab en la
  EC2.

## Resultado de la Decisión

**Opción elegida: A (reusar Dagster).**

**Por qué:**

- **Un solo orquestador, ya operado por el equipo:** no se suma un servicio ni
  una curva de aprendizaje nueva; el retrain hereda idempotencia, retries con
  backoff y observabilidad de las mismas primitivas del
  [ADR-0009](0009-orquestador-dagster.md).
- **El retrain se dispara por cambio de datos:** el asset de training declara
  dependencia sobre el modelo gold (`get_asset_key_for_model` →
  `fct_produccion_pozo_mes`), de modo que re-materializar una partición
  `fecha_extraccion` reentrena y registra una versión nueva en MLflow. Ese es
  el trigger de reentrenamiento que pide la adenda, sin cablearlo a mano.
- **Idempotencia y "repetir para un día dado" ya resueltas:** las particiones
  diarias (`DailyPartitionsDefinition`) usadas en bronze/raw/dbt se reusan tal
  cual; correr la partición dos veces produce el mismo run reproducible.
- **Lineage continuo datos → features → modelo:** al ser todo assets en la
  misma UI, el linaje `gold → feature mart → modelo → registry` queda visible
  de punta a punta y exportable a DataHub
  ([ADR-0016](0016-gobierno-de-datos-datahub.md)).
- **El cómputo es CPU y encaja en la instancia:** Arps + GBM sobre datos
  tabulares no necesita GPUs ni un cluster; corre en la EC2 con el resto del
  stack.

**Contra las alternativas:** Airflow (B) duplicaría un orquestador para lo
mismo, con más RAM y sin el modelo asset-céntrico que da el lineage
datos↔modelo. Kubeflow/Metaflow (C) son potentes para ML a escala sobre
Kubernetes, pero su valor —GPUs, entrenamiento distribuido, pipelines
efímeros— no aplica a un modelo CPU mensual, y traen un plano de control
(Kubernetes) desproporcionado para una EC2 con Docker Compose. cron (D) no
cumple los MUST: sin retries declarativos, sin UI de status, sin trigger por
cambio de datos ni lineage.

### Consecuencias

- **Bueno, porque:** datos y ML comparten orquestador, lineage y UI; el
  retrain se dispara re-materializando la partición o por `@schedule`, y es
  reproducible por `fecha_extraccion`.
- **Bueno, porque:** los assets de ML se testean en pytest dentro del CI
  existente, igual que los del pipeline de datos, y el gate de validación
  ([ADR-0024](0024-cicd-del-pipeline-de-ml.md)) se ejecuta como un asset más.
- **Malo, porque:** acopla el ciclo de vida del training al de la plataforma
  de datos (misma imagen e instancia); si el entrenamiento creciera a
  GPU/distribuido, Dagster seguiría orquestando pero el cómputo habría que
  externalizarlo.
- **Malo, porque:** la imagen del code-server de Dagster suma las
  dependencias de ML (mlflow, scikit-learn, etc.), engordando el contenedor.

### Confirmación

Se verifica con: `pipeline/assets/ml.py` definiendo el grupo `ml` y el
`ml_training_job` + `@schedule` en `pipeline/definitions.py`; la dependencia
del asset de training sobre el modelo gold vía `get_asset_key_for_model`; los
runs del job visibles en la UI de Dagster; y una re-materialización de la
partición disparando un retrain que registra una versión nueva en MLflow.
