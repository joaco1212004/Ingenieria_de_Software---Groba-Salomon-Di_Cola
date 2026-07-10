# Grupo ml: entrenamiento recurrente del modelo de declino (ADR-0019/0022).
# Flujo: fct_features_declino (dbt, build_features) -> entrenamiento_m3 ->
# validacion_m3 (gate champion/challenger) -> registro_m3 (Model Registry).
#
# Re-materializar una particion fecha_extraccion reentrena con la misma semilla
# y params (run reproducible) y registra una version nueva en MLflow: ese es el
# trigger de retrain por cambio de datos que pide la adenda.
#
# Los assets solo necesitan MLFLOW_TRACKING_URI: el server de MLflow proxea los
# artefactos (--serve-artifacts), nadie reparte credenciales del object store.

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

import pandas as pd
from dagster import AssetExecutionContext, Failure, MaterializeResult, Output, asset
from dagster_dbt import get_asset_key_for_model

from pipeline.assets.bronze import fecha_extraccion_partitions
from pipeline.assets.dbt import medallion_dbt_assets
from pipeline.ml.config import config_from_env
from pipeline.ml.datos import preparar_cohorte
from pipeline.ml.m3 import N_ESTATICO, entrenar_m3
from pipeline.ml.registry import (
    EXPERIMENT,
    MODEL_NAME,
    METRICA_GATE,
    evaluar_gate,
    metricas_de_produccion,
    registrar_y_promover,
)
from pipeline.resources.postgres import postgres_engine_from_env

FEATURES_QUERY = (
    "select idpozo, fecha_periodo, tasa_diaria_pet from gold.fct_features_declino"
)


def cargar_features() -> pd.DataFrame:
    """Lee el feature mart del warehouse (los tests la reemplazan por un DF sintetico)."""
    return pd.read_sql(FEATURES_QUERY, postgres_engine_from_env())


def _mlflow_configurado():
    import mlflow

    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    mlflow.set_experiment(EXPERIMENT)
    return mlflow


@asset(
    group_name="ml",
    partitions_def=fecha_extraccion_partitions,
    deps=[get_asset_key_for_model([medallion_dbt_assets], "fct_features_declino")],
    description=(
        "Entrena M3 (Arps + LSTM residual) sobre la tasa diaria del feature "
        "mart y loggea params, metricas y artefactos como run de MLflow."
    ),
)
def entrenamiento_m3(context: AssetExecutionContext) -> Output:
    cfg = config_from_env()
    fecha = context.partition_key

    df = cargar_features()
    cohorte = preparar_cohorte(df, cfg)
    if not cohorte["series"]:
        raise Failure(
            f"cohorte vacia para la particion {fecha}: gold.fct_features_declino "
            "no tiene pozos con historia suficiente (corre el medallion_daily_job "
            "con datos reales antes de entrenar)"
        )
    folds = {k: len(v) for k, v in cohorte["folds"].items()}
    context.log.info("Cohorte: %d pozos | folds %s", len(cohorte["series"]), folds)

    mlflow = _mlflow_configurado()
    with mlflow.start_run(run_name=f"m3-{fecha}") as run:
        mlflow.set_tags(
            {
                "fecha_extraccion": fecha,
                "dagster_run_id": context.run_id,
                "modelo": "M3",
            }
        )
        mlflow.log_params(
            {
                **asdict(cfg),
                "n_pozos": len(cohorte["series"]),
                "fold_train": folds["train"],
                "fold_val": folds["val"],
                "fold_test": folds["test"],
            }
        )

        def log_epoca(registro: dict) -> None:
            mlflow.log_metrics(
                {
                    "train_loss": registro["train/loss"],
                    "val_loss": registro["val/loss"],
                },
                step=registro["epoch"],
            )

        try:
            model, info, resumen, _ = entrenar_m3(cohorte, cfg, log_fn=log_epoca)
        except ValueError as exc:
            raise Failure(f"entrenamiento M3 fallo para {fecha}: {exc}") from exc

        mlflow.log_metrics({k: float(v) for k, v in resumen.items()})
        mlflow.pytorch.log_model(model, "model")
        # lo que necesita el serving para reconstruir el predictor (la
        # inferencia re-ajusta Arps por pozo: LSTM + config es todo el artefacto)
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "n_estatico": N_ESTATICO,
                        "horizonte": cfg.horizonte,
                        "use_changepoint": cfg.use_changepoint,
                        "target": cfg.target,
                    }
                )
            )
            mlflow.log_artifact(str(config_path))

        run_id = run.info.run_id

    context.log.info(
        "Run %s: %d epocas | test log_mae=%.4f",
        run_id,
        info["epocas"],
        resumen["log_mae"],
    )
    return Output(
        {"run_id": run_id, "metricas": resumen},
        metadata={
            "mlflow_run_id": run_id,
            "epocas": info["epocas"],
            **{k: float(v) for k, v in resumen.items()},
        },
    )


@asset(
    group_name="ml",
    partitions_def=fecha_extraccion_partitions,
    description=(
        "Gate champion/challenger: compara las metricas de test del run nuevo "
        "contra la version en Production. Retener no es un error: la version "
        "queda en Staging."
    ),
)
def validacion_m3(context: AssetExecutionContext, entrenamiento_m3: dict) -> Output:
    from mlflow.tracking import MlflowClient

    _mlflow_configurado()
    challenger = entrenamiento_m3["metricas"]
    champion = metricas_de_produccion(MlflowClient(), MODEL_NAME)
    gate_paso = evaluar_gate(challenger, champion)

    champion_metric = champion.get(METRICA_GATE) if champion else None
    context.log.info(
        "Gate %s: challenger %s=%.4f vs champion %s",
        "PASA" if gate_paso else "RETIENE",
        METRICA_GATE,
        challenger[METRICA_GATE],
        f"{champion_metric:.4f}" if champion_metric is not None else "(no hay)",
    )
    return Output(
        {**entrenamiento_m3, "gate_paso": gate_paso},
        metadata={
            "gate_paso": gate_paso,
            f"challenger_{METRICA_GATE}": float(challenger[METRICA_GATE]),
            f"champion_{METRICA_GATE}": (
                float(champion_metric)
                if champion_metric is not None
                else "sin champion"
            ),
        },
    )


@asset(
    group_name="ml",
    partitions_def=fecha_extraccion_partitions,
    description=(
        "Registra la version nueva en el Model Registry (None -> Staging) y la "
        "promueve a Production si el gate paso, archivando la anterior."
    ),
)
def registro_m3(
    context: AssetExecutionContext, validacion_m3: dict
) -> MaterializeResult:
    from mlflow.tracking import MlflowClient

    _mlflow_configurado()
    version, stage = registrar_y_promover(
        MlflowClient(), validacion_m3["run_id"], validacion_m3["gate_paso"]
    )
    context.log.info("%s v%d -> %s", MODEL_NAME, version, stage)
    return MaterializeResult(
        metadata={
            "modelo": MODEL_NAME,
            "version": version,
            "stage": stage,
            "mlflow_run_id": validacion_m3["run_id"],
        }
    )
