"""Tests de los assets del grupo ml: pipeline train -> validate -> register.

Sin servidor: MLflow usa el file store local (tmp_path), que soporta tracking
y Model Registry. El feature mart se reemplaza patcheando `cargar_features`
(mismo espiritu que el mock HTTP de los tests de bronze).
"""

from __future__ import annotations

import mlflow
import pytest
from dagster import materialize
from mlflow.tracking import MlflowClient

from pipeline.assets.ml import entrenamiento_m3, registro_m3, validacion_m3
from pipeline.ml.registry import MODEL_NAME

PARTITION = "2026-06-10"


@pytest.fixture
def entorno_mlflow(tmp_path, monkeypatch, df_declino):
    """Tracking en file store temporal + cohorte sintetica + smoke config."""
    tracking_uri = f"file://{tmp_path}/mlruns"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", tracking_uri)
    monkeypatch.setenv("ML_EPOCHS", "3")
    monkeypatch.setattr("pipeline.assets.ml.cargar_features", lambda: df_declino)
    # el modulo mlflow es global: fijar la URI tambien en el proceso de test
    mlflow.set_tracking_uri(tracking_uri)
    return tracking_uri


def test_ml_pipeline_entrena_y_promueve(entorno_mlflow):
    resultado = materialize(
        [entrenamiento_m3, validacion_m3, registro_m3],
        partition_key=PARTITION,
    )
    assert resultado.success

    client = MlflowClient()
    experimento = client.get_experiment_by_name("declino-pozos")
    assert experimento is not None
    runs = client.search_runs([experimento.experiment_id])
    assert len(runs) == 1
    run = runs[0]
    assert run.info.run_name == f"m3-{PARTITION}"
    # reproducibilidad: semilla e hiperparametros loggeados como params
    assert run.data.params["seed"] == "42"
    assert run.data.params["hidden"] == "64"
    assert run.data.params["lr"] == "0.0005"
    assert run.data.tags["fecha_extraccion"] == PARTITION
    assert "log_mae" in run.data.metrics
    assert "train_loss" in run.data.metrics

    # primer run: no hay champion -> la version 1 queda en Production
    versiones = client.get_latest_versions(MODEL_NAME, stages=["Production"])
    assert len(versiones) == 1
    assert int(versiones[0].version) == 1


def test_ml_gate_retiene_en_staging(entorno_mlflow):
    # champion imbatible pre-sembrado: run con log_mae ~perfecto en Production
    client = MlflowClient()
    mlflow.set_experiment("declino-pozos")
    with mlflow.start_run(run_name="champion-imbatible") as run:
        mlflow.log_metric("log_mae", 1e-6)
    client.create_registered_model(MODEL_NAME)
    mv = client.create_model_version(
        MODEL_NAME, source=f"{run.info.artifact_uri}/model", run_id=run.info.run_id
    )
    client.transition_model_version_stage(MODEL_NAME, mv.version, stage="Production")

    resultado = materialize(
        [entrenamiento_m3, validacion_m3, registro_m3],
        partition_key=PARTITION,
    )
    assert resultado.success

    # el gate retiene: la version nueva existe pero queda en Staging
    nueva = client.get_model_version(MODEL_NAME, int(mv.version) + 1)
    assert nueva.current_stage == "Staging"
    produccion = client.get_latest_versions(MODEL_NAME, stages=["Production"])
    assert int(produccion[0].version) == int(mv.version)


def test_ml_entrenamiento_falla_con_cohorte_vacia(tmp_path, monkeypatch, df_declino):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"file://{tmp_path}/mlruns")
    # cohorte vacia: series demasiado cortas para el split temporal
    vacio = df_declino.groupby("idpozo").head(4).reset_index(drop=True)
    monkeypatch.setattr("pipeline.assets.ml.cargar_features", lambda: vacio)

    resultado = materialize(
        [entrenamiento_m3], partition_key=PARTITION, raise_on_error=False
    )
    assert not resultado.success
