"""Libreria de ML del pipeline de entrenamiento (ADR-0019 / ADR-0022).

Port del modelo M3 (Arps + LSTM sobre el residual log) desde el repo de
investigacion DCA (Produccion-de-petroleo-proyecto-ML, informe v2.0), adaptado
a este stack: los datos vienen del feature mart gold (`fct_features_declino`)
en vez de un parquet local, y el tracking va a MLflow en vez de W&B.

Paquete puro (sin imports de Dagster): los assets de `pipeline/assets/ml.py`
lo orquestan y los tests lo ejercitan directo.
"""
