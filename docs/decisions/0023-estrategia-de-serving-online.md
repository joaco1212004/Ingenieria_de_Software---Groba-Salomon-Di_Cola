# Serving online: la API carga el modelo Production del registry

## Contexto y Declaración del Problema

La Adenda 3 exige que los usuarios consuman **una API REST que permita hacer
uso del servicio** de pronóstico. Con el modelo entrenado, validado y
promovido en MLflow ([ADR-0019](0019-experiment-tracking-y-model-registry-mlflow.md),
[ADR-0024](0024-cicd-del-pipeline-de-ml.md)) y las features en el mart de gold
([ADR-0020](0020-feature-store-dbt-mart.md)), falta decidir **cómo llegan las
predicciones al endpoint** `GET /api/v1/forecast`, que en Fase 1/2 era un mock
que devolvía historia del warehouse.

Restricciones del caso: el modelo (M3, Arps + LSTM sobre el residual,
[ADR-0022](0022-orquestacion-del-entrenamiento.md)) re-ajusta la curva de
declino con la historia del pozo en cada inferencia y predice cualquier
horizonte futuro de meses; el KPI de latencia de la API es p99 < 5 s; y el
video de la entrega debe mostrar un retrain cuyo modelo nuevo pasa a ser
servido.

## Factores de Decisión

- Flexibilidad del contrato: el usuario pide un pozo y un rango de fechas
  futuras arbitrario.
- Frescura del modelo: un retrain promovido debe reflejarse en las respuestas
  sin redeploy de la API (MUST de "despliegue recurrente y automático").
- Latencia dentro del KPI (p99 < 5 s) en la instancia chica (EC2-1).
- Comportamiento ante fallas: qué responde la API sin modelo en Production o
  con un pozo sin historia suficiente.
- Simplicidad operativa: componentes nuevos a mantener.

## Opciones Consideradas

- **Opción A — Serving online.** La API carga el modelo en stage `Production`
  desde el registry (cache en memoria con TTL), trae la serie del pozo del
  feature mart y predice en el request.
- **Opción B — Batch precomputado.** El pipeline de Dagster precalcula las
  predicciones de todos los pozos a una tabla gold (p. ej.
  `fct_forecast_pozo_mes`) y la API solo la consulta.
- **Opción C — Híbrido.** Batch precomputado para un horizonte estándar +
  cómputo online para rangos no cubiertos.

## Resultado de la Decisión

**Opción elegida: A (serving online).**

**Por qué:**

- **El contrato es arbitrario y el batch no lo cubre:** el usuario pide
  cualquier `date_start/date_end` futuro. Precomputar exige fijar horizonte y
  momento de corte por pozo; cualquier pedido fuera de eso vuelve a necesitar
  el camino online. Online sirve cualquier rango con una sola implementación.
- **Frescura sin redeploy:** la API consulta el registry con un cache TTL de
  5 minutos: cuando un retrain promueve una versión nueva
  ([ADR-0024](0024-cicd-del-pipeline-de-ml.md)), el serving la adopta solo.
  Es además lo que el video debe demostrar (retrain → la API sirve el modelo
  nuevo, visible en el campo `model_version` de la respuesta).
- **La latencia entra holgada en el KPI:** la inferencia por pozo es un ajuste
  de curva (scipy) + un forward de una LSTM chica en CPU + una query indexada
  de la historia del pozo — bien por debajo de p99 < 5 s. El costo pesado (el
  entrenamiento) ya ocurre fuera del request, en Dagster.
- **Errores explícitos, sin fallback a historia:** sin modelo en Production,
  con historia insuficiente o si el declino no ajusta, la API responde **503
  (o 404 si el pozo no existe)** con detalle, en vez de degradar a devolver
  historia como el mock. Devolver historia disfrazada de pronóstico sería
  silenciosamente incorrecto para el usuario; el error honesto es diagnóstico
  y observable (métrica `predictiva_forecasts_generated_total{status}`).
- **Consistencia con el feature store:** el retrieval online lee el mismo mart
  que el training ([ADR-0020](0020-feature-store-dbt-mart.md)) — features
  persistidas y usadas en inferencia, como exige la adenda.

**Contra las alternativas:** el batch (B) da latencia mínima y aísla a la API
de MLflow, pero congela horizonte y frescura (cada retrain obliga a recomputar
toda la tabla), no responde rangos arbitrarios, y desacopla la predicción del
`model_version` que la sirve — más una tabla más que mantener. El híbrido (C)
paga la complejidad de ambos mundos (dos caminos de código, dos fuentes de
verdad para la misma pregunta) para optimizar una latencia que ya cumple el
KPI sin ayuda.

### Consecuencias

- **Bueno, porque:** un solo camino de código sirve cualquier rango futuro,
  adopta retrains automáticamente y expone la versión servida en la respuesta
  y en Prometheus (`predictiva_model_version`).
- **Bueno, porque:** la degradación es controlada: registry caído con modelo
  cacheado → se sirve el cache; sin cache → 503 con detalle; los estados de
  error son observables por métricas.
- **Malo, porque:** la API depende en runtime de MLflow (EC2-2) para el primer
  load y los refresh — mitigado por el cache TTL y la degradación suave, pero
  si EC2-2 está apagada y la API reinicia, el forecast responde 503 hasta que
  vuelva.
- **Malo, porque:** el costo de inferencia se paga por request; si el tráfico
  creciera órdenes de magnitud, habría que sumar un cache de respuestas o
  migrar a C (el diseño lo permite sin tirar nada).

### Confirmación

Se verifica con: `api/ml_model.py` (carga de `models:/declino-pozos-m3/Production`
con cache TTL y recarga al cambiar la versión), `api/feature_client.py`
(retrieval del mart de gold) y `api/forecast/routes.py` (predicción real,
errores 400/404/503); `tests/test_predictions.py` cubriendo todos los caminos;
y la demo del video: un retrain promovido cambia el `model_version` que la API
devuelve, sin redeploy.
