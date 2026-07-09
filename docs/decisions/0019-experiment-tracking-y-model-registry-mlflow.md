# MLflow para experiment tracking y model registry

## Contexto y Declaración del Problema

La Adenda 3 exige **una plataforma que permita el tracking del entrenamiento
de modelos de modo que el mismo sea reproducible**, y que el modelo servido
por la API ([ADR-0023](0023-estrategia-de-serving-online.md)) sea una versión
concreta, versionada y promovible. Hacen falta entonces dos capacidades: (1)
un registro de *runs* de entrenamiento con sus parámetros, métricas y
artefactos (para comparar corridas y reproducirlas), y (2) un **model
registry** con estados (p. ej. `Production`) desde el cual la API carga el
modelo vigente.

El equipo ya venía prototipando el entrenamiento con Weights & Biases, así
que la elección es también si se sigue con ese SaaS o se autogestiona una
plataforma sobre la infraestructura ya construida en Fase 2: PostgreSQL
([ADR-0012](0012-warehouse-postgresql.md)) y el object store S3/MinIO
([ADR-0010](0010-datalake-bronze-s3.md)).

## Factores de Decisión

- Cumplimiento del MUST de tracking reproducible: params, métricas,
  artefactos y semilla por run, comparables entre corridas.
- Model registry con transiciones de estado que la API pueda consumir para
  el serving online ([ADR-0023](0023-estrategia-de-serving-online.md)).
- Reuso de la infra existente (Postgres + MinIO) vs sumar un servicio o un
  SaaS con costo/límites.
- Soberanía de los datos: runs y artefactos dentro de la infra del equipo,
  sin depender de una cuenta SaaS externa ni de créditos de AWS Academy que
  vencen.
- Fricción de migración desde el prototipo en Weights & Biases.
- Integración con el orquestador Dagster
  ([ADR-0009](0009-orquestador-dagster.md)), que loggea cada run del job de
  training.

## Opciones Consideradas

- **Opción A — MLflow self-hosted.** Servidor open source con *backend
  store* en Postgres (runs, params, métricas, registry) y *artifact store*
  en MinIO. Tracking, UI de comparación de runs y model registry con estados
  en una sola herramienta.
- **Opción B — Weights & Biases.** SaaS de experiment tracking con UI muy
  pulida y baja fricción, con model registry y artefactos en su nube.
- **Opción C — Neptune.** SaaS de tracking de perfil similar a W&B,
  orientado a metadata de experimentos.
- **Opción D — DVC.** Versionado de datos y pipelines sobre Git + storage
  remoto, con `dvc exp` para experimentos.

## Resultado de la Decisión

**Opción elegida: A (MLflow self-hosted, backend Postgres + artefactos
MinIO).**

**Por qué:**

- **Reusa la infra de Fase 2, sin costo ni credenciales nuevas:** el backend
  store va sobre el PostgreSQL existente ([ADR-0012](0012-warehouse-postgresql.md))
  y los artefactos en MinIO ([ADR-0010](0010-datalake-bronze-s3.md)). No se
  suma un SaaS ni se depende de un plan gratuito con límites de storage o
  colaboradores.
- **Model registry con estados, que es lo que consume la API:** MLflow
  registra versiones y las transiciona (`None → Staging → Production`); la API
  carga el modelo en stage `Production` para servir predicciones
  ([ADR-0023](0023-estrategia-de-serving-online.md)). Es el pilar del gate
  champion/challenger ([ADR-0024](0024-cicd-del-pipeline-de-ml.md)).
- **Soberanía y reproducibilidad:** runs y artefactos quedan en la infra del
  equipo; un snapshot por `fecha_extraccion` y la semilla loggeada permiten
  reproducir cualquier corrida sin depender de un tercero.
- **Proxy de artefactos = clientes sin credenciales de object store:** con
  `--serve-artifacts` el servidor intermedia el acceso a MinIO, así el job de
  Dagster, la máquina de un dev (incluida una GPU local) y la API sólo
  necesitan la URL de tracking. Esto abarató la migración desde W&B: el dev
  cambia `MLFLOW_TRACKING_URI` y las llamadas `wandb.log(...)` por
  `mlflow.log_*` casi 1:1.
- **Integración natural con el stack Python/Dagster:** el asset de training
  ([ADR-0022](0022-orquestacion-del-entrenamiento.md)) loggea params,
  métricas y artefactos por run con la librería estándar de MLflow.

**Contra las alternativas:** Weights & Biases (B) tiene el mejor tracking en
fricción y UI, pero es SaaS: el registry y los artefactos viven en su nube, el
plan gratis limita storage/colaboradores y los datos salen de la infra propia;
migrar de W&B a MLflow fue barato justamente porque su API de logging es
análoga. Neptune (C) comparte el perfil SaaS de B, sin ventaja que justifique
la dependencia externa. DVC (D) versiona datos y pipelines sobre Git, pero no
ofrece un servidor de tracking con UI de comparación de runs ni un model
registry con estados/transiciones: habría que combinarlo con otras
herramientas para cubrir lo que MLflow trae integrado.

### Consecuencias

- **Bueno, porque:** el tracking reproducible y el registry con estados se
  cubren con una sola herramienta montada sobre Postgres + MinIO ya
  existentes, a costo cero y con los datos en casa.
- **Bueno, porque:** el proxy de artefactos deja a todos los clientes
  (Dagster, GPU de un dev, API) hablando sólo con la URL de tracking, sin
  repartir credenciales de S3/MinIO.
- **Malo, porque:** es un servicio más para hostear y mantener; corre en la
  instancia grande (EC2-2) junto a Metabase y DataHub por consumo de RAM, no
  en la instancia chica que sirve la API.
- **Malo, porque:** al autogestionar backend y artefactos, el backup y la
  retención son responsabilidad del equipo (un SaaS los daría gestionados); y
  la UI queda sin autenticación por defecto —mismo criterio que el resto de
  las UIs del TP—, a restringir por security group.

### Confirmación

Se verifica con: el servicio definido en
`infra/mlflow/docker-compose.mlflow.yml` (server + Postgres + MinIO propios)
deployado a EC2-2 por `deploy-platforms.yml`; el endpoint `/health`
respondiendo en el puerto 5000; runs con params y métricas visibles y
comparables en la UI de MLflow durante la demo (varias corridas del job de
training); y el model registry mostrando la versión en stage `Production` que
la API carga para servir predicciones.
