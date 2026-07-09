# CI/CD del pipeline de ML con gate de validación champion/challenger

## Contexto y Declaración del Problema

La Adenda 3 pide que **el entrenamiento y despliegue de modelos sea recurrente
y automático** y que **los pipelines se desplieguen mediante CI/CD**. Con el
tracking y el registry resueltos en MLflow
([ADR-0019](0019-experiment-tracking-y-model-registry-mlflow.md)) y el training
orquestado por Dagster ([ADR-0022](0022-orquestacion-del-entrenamiento.md)),
falta decidir **cómo un modelo recién entrenado llega (o no) al stage
`Production`** que la API sirve ([ADR-0023](0023-estrategia-de-serving-online.md)).

El riesgo a evitar: que un retrain con datos degradados o un bug en las
features **pise el modelo en `Production`** y la API empiece a servir
predicciones peores sin que nadie lo note.

## Factores de Decisión

- Cumplimiento de los MUST: retrain recurrente/automático y pipelines por
  CI/CD ([ADR-0004](0004-ci-con-github-actions.md)).
- Prevención de regresiones: no promover un modelo peor que el vigente.
- Reproducibilidad y trazabilidad de la promoción.
- Reuso del CI existente (GitHub Actions) y del model registry de MLflow.
- Dónde vive el control: en el CI (por PR) y/o en el pipeline de retrain (por
  corrida productiva).

## Opciones Consideradas

- **Opción A — Gate de validación champion/challenger en CI/CD.** El retrain
  registra el modelo nuevo como *challenger*; se promueve a `Production` sólo
  si supera al *champion* vigente en el backtest temporal. Un job `ml-ci` en
  GitHub Actions corre además los tests de `ml/` y la lógica del gate en cada
  PR.
- **Opción B — Deploy manual.** Un humano evalúa cada modelo y lo promueve a
  mano en MLflow.
- **Opción C — Promoción automática sin gate.** Cada retrain transiciona
  automáticamente su modelo a `Production`.

## Resultado de la Decisión

**Opción elegida: A (gate champion/challenger en CI/CD).**

**Por qué:**

- **Automático sin sacrificar seguridad:** el retrain corre solo (schedule o
  re-materialización de partición, [ADR-0022](0022-orquestacion-del-entrenamiento.md)),
  pero la transición a `Production` queda condicionada a superar al champion en
  métricas de holdout temporal (MAE/MAPE/RMSE). Cumple el MUST de "recurrente y
  automático" y a la vez blinda contra regresiones.
- **Dos capas de control, ambas como código:** (1) el job `ml-ci` en
  `ci.yml` corre los tests de `ml/` (ajuste de declino determinista, features,
  lógica del gate) en cada PR, así un cambio de código no rompe el pipeline
  antes de mergear; (2) el asset `validate_model` en Dagster aplica el gate en
  cada retrain productivo, antes de `register/promote`.
- **Reproducible y trazable:** la comparación challenger vs champion queda
  loggeada en MLflow (métricas de ambas versiones) y la transición de stage es
  un evento auditable en el registry.
- **Reusa lo existente:** se apoya en el CI de GitHub Actions
  ([ADR-0004](0004-ci-con-github-actions.md)) y en el registry de MLflow
  ([ADR-0019](0019-experiment-tracking-y-model-registry-mlflow.md)); no suma
  infraestructura.

**Contra las alternativas:** el deploy manual (B) viola el MUST de "automático"
y no escala a retrains recurrentes: depende de que alguien recuerde evaluar y
promover. La promoción automática sin gate (C) es automática pero peligrosa —
un retrain con datos malos o un bug de features pisa `Production` y la API
sirve predicciones peores en silencio; es exactamente el escenario que el
champion/challenger previene.

### Consecuencias

- **Bueno, porque:** el modelo en `Production` sólo mejora o se mantiene; las
  regresiones se bloquean por métricas, no por vigilancia humana.
- **Bueno, porque:** el gate vive versionado y testeado (asset
  `validate_model` + job `ml-ci`), reproducible en cada PR y cada retrain.
- **Malo, porque:** define un umbral/criterio de comparación que hay que
  calibrar (qué margen de mejora se exige, qué métrica manda) — una decisión de
  modelado (Rol 1, ver el ADR del gate de validación) que este pipeline
  parametriza, no fija.
- **Malo, porque:** requiere un caso base para el primer modelo (cuando no hay
  champion): se promueve el primero contra un baseline naive (p. ej. persistir
  el último valor) en lugar de incondicionalmente.

### Confirmación

Se verifica con: el job `ml-ci` en `.github/workflows/ci.yml` corriendo los
tests de `ml/` y del gate en cada PR; el asset `validate_model` comparando
challenger vs champion en el backtest temporal y promoviendo en MLflow sólo si
supera el umbral; y una demostración con dos retrains — uno que **no** promueve
(challenger peor) y uno que **sí**—, con la API sirviendo la versión resultante.
