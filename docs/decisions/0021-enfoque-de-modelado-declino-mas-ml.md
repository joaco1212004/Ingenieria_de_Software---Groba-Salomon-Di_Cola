# Enfoque de modelado: curva de declino de Arps + corrección ML (M3)

## Contexto y Declaración del Problema

La Adenda 3 exige un modelo que pronostique la **producción mensual de
petróleo por pozo** (`prod_pet`, grano pozo × año × mes) a partir de la
historia en `gold.fct_features_declino` ([ADR-0020](0020-feature-store-dbt-mart.md)).
El dominio impone dos restricciones que cualquier enfoque tiene que resolver:

- **Downtime operativo vs declino físico**: un pozo parado un mes colapsa el
  volumen mensual sin que el reservorio haya declinado. Por eso se modela la
  **tasa diaria** `tasa_diaria_pet = prod_pet / tef` (NULL cuando `tef <= 0`,
  nunca 0), que aísla la señal física del ruido operativo.
- **Miles de pozos heterogéneos, historias cortas**: la industria petrolera
  ya tiene un modelo físico estándar para el declino de producción — la curva
  de Arps —, pero cada pozo individual tiene pocos meses de historia para
  ajustar un modelo puramente estadístico por sí solo.

## Factores de Decisión

- Precisión de pronóstico medida honestamente: evaluación en pozos y meses
  que el modelo **nunca vio** en entrenamiento (no fuga temporal ni de pozo).
- Capacidad de generalizar entre pozos con poca historia individual
  (mínimo 12 meses, 6 con producción positiva) sin sobreajustar por pozo.
- Interpretabilidad frente al dominio: un ingeniero de reservorios reconoce
  y puede auditar los parámetros del ajuste (tipo de curva, tasa inicial,
  declino).
- Cómputo disponible: CPU únicamente, entrenamiento recurrente en Dagster
  ([ADR-0022](0022-orquestacion-del-entrenamiento.md)) sobre una EC2 sin GPU.
- Reproducibilidad y comparabilidad para el gate champion/challenger
  ([ADR-0024](0024-cicd-del-pipeline-de-ml.md)): una métrica primaria estable
  entre reentrenamientos.

## Opciones Consideradas

- **Opción A — Curva de declino (Arps) + corrección ML sobre el residuo.**
  Se ajusta una curva de Arps clásica por pozo sobre el tramo post-pico de
  producción; una red LSTM **global** (entrenada sobre todos los pozos del
  fold de train) aprende a corregir, en escala logarítmica, lo que la curva
  no explica mes a mes.
- **Opción B — Series de tiempo clásicas por pozo (ARIMA/Prophet).** Un
  modelo independiente ajustado a la serie histórica de cada pozo.
- **Opción C — GBM (gradient boosting) global puro.** Un único modelo de
  boosting sobre features tabulares (lags, medias móviles, categóricas de
  pozo/área/empresa) sin curva física de por medio.

## Resultado de la Decisión

**Opción elegida: A (Arps + corrección ML, modelo "M3").**

**Por qué:**

- **La curva de Arps aporta el prior físico que compensa la poca historia
  individual**: `ArpsBaseline` ajusta, por pozo, la mejor de tres formas
  clásicas de declino (exponencial `qi·e^(-di·t)`, armónica `qi/(1+di·t)`,
  hiperbólica `qi/(1+b·di·t)^(1/b)`) sobre el tramo posterior al pico de
  producción (`detect_peak`), eligiendo por menor log-MAE de ajuste. Con 12
  meses de historia alcanza para una curva de 2-3 parámetros; no alcanzaría
  para entrenar una red por pozo desde cero.
- **La corrección aprende de TODOS los pozos, sin perder especificidad por
  pozo**: la LSTM es un único modelo global (`LSTMResidual`) que recibe la
  secuencia de residuos logarítmicos del ajuste de Arps de train
  (`[residual_log, log1p(base_arps), observado]`) más un vector estático de
  8 features (parámetros del ajuste + tipo de curva) y predice 60 meses de
  corrección directa —no autoregresiva—, evitando la acumulación de error
  del sampling paso a paso. Cada pozo individual aporta poca señal, pero
  entre miles de pozos hay patrones sistemáticos de sobre/sub-declino que un
  ajuste de Arps aislado no captura.
- **Predicción final interpretable**: `q̂(t) = expm1(log1p(arps(t)) +
  corrección(t − k_tr))`. La curva pone la tendencia física; la corrección es
  auditable como desviación relativa de esa tendencia, no una caja negra que
  reemplaza el juicio de dominio.
- **Evaluación sin fuga, en dos ejes**: split temporal dentro de cada pozo
  (train 60% / val 20% / test último 20%, `split_temporal_602020`) *y* split
  a nivel pozo (`split_pozos`, 60/20/20 estratificado por longitud de
  historia) — el modelo se evalúa en pozos que **jamás vio** durante el
  entrenamiento, no solo en meses futuros de pozos conocidos. Para pozos
  cerrados (sin reportar hace ≥12 meses) el acumulado observado es la EUR
  real, lo que habilita una métrica adicional (`r2_eur`) contra ese
  subconjunto "gold" de verdad conocida.
- **Costo de cómputo compatible con CPU**: Arps se ajusta con `scipy.optimize`
  (liviano) y la LSTM es chica (`hidden=64`, capas=1); todo el entrenamiento
  corre en la EC2 sin GPU dentro del schedule diario de Dagster.
- **Métrica primaria estable para el gate**: `log_mae` (MAE en escala
  `log1p`, robusta a la escala heterogénea de producción entre pozos chicos y
  grandes) es la que compara el ADR-0024 entre challenger y champion.

**Contra las alternativas:** ARIMA/Prophet por pozo (B) ajustan un modelo
independiente por serie, lo que con 12-24 meses de historia por pozo
sobreajusta con facilidad y no comparte información entre pozos similares del
mismo yacimiento; además, miles de ajustes independientes escalan peor en
CPU que un único modelo global más un ajuste de curva liviano por pozo. GBM
global puro (C) comparte información entre pozos igual que la opción elegida,
pero sin la curva de Arps como prior pierde la tendencia física de largo
plazo del declino: sobre un horizonte de 60 meses tiende a degradar hacia el
promedio de entrenamiento en vez de seguir la trayectoria de declino
esperable para cada tipo de pozo, y resigna la interpretabilidad de dominio
que valoran los ingenieros de reservorios.

### Consecuencias

- **Bueno, porque:** el modelo combina el conocimiento de dominio (Arps) con
  la capacidad de generalización de un modelo global (LSTM), evaluado sin
  fuga en pozos nunca vistos.
- **Bueno, porque:** los parámetros de Arps por pozo (tipo de curva, tasa
  inicial, declino) quedan disponibles como diagnóstico, no solo como
  insumo de la predicción.
- **Bueno, porque:** la métrica primaria (`log_mae`) y la evaluación en
  pozos cerrados (EUR real) dan una noción de calidad más rica que un único
  número agregado, útil tanto para el gate automático como para revisión
  humana.
- **Malo, porque:** si un pozo no tiene suficiente historia post-pico para
  que Arps ajuste (`arps.fitted == False`), el pozo queda fuera del
  entrenamiento y de la inferencia — el serving online
  ([ADR-0023](0023-estrategia-de-serving-online.md)) responde 503 en ese
  caso en vez de forzar una predicción sin base física.
- **Malo, porque:** el enfoque tiene dos partes móviles (ajuste clásico +
  red neuronal) en vez de una sola, lo que exige mantener y versionar ambas
  piezas de lógica (`pipeline/ml/arps.py` y `pipeline/ml/m3.py`) en sincronía.

### Confirmación

Se verifica con: `pipeline/ml/arps.py` (ajuste de las tres curvas y
detección de pico), `pipeline/ml/m3.py` (preparación por pozo, la red
`LSTMResidual` y `entrenar_m3`), `pipeline/ml/evaluacion.py` (`log_mae`,
`rmse`, `r2_eur` sobre pozos cerrados) y `pipeline/ml/datos.py` (los dos
splits sin fuga); los tests en `tests/pipeline/test_ml_m3.py` (ajuste
determinista de Arps, shapes de `preparar_pozo`, smoke de entrenamiento); y
en la demo, la comparación de métricas entre corridas en la UI de MLflow
([ADR-0019](0019-experiment-tracking-y-model-registry-mlflow.md)).
