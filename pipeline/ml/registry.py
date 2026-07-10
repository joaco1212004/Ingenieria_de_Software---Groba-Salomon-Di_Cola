"""Model Registry de MLflow: gate de metricas y promocion (ADR-0019).

El flujo de estados es None -> Staging -> Production: toda version nueva entra
en Staging; el gate compara sus metricas de test contra las del champion (la
version actualmente en Production) y solo promueve si no empeora. La API de
serving (futuro ADR-0023) carga siempre el stage Production.
"""

from __future__ import annotations

from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

EXPERIMENT = "declino-pozos"
MODEL_NAME = "declino-pozos-m3"
METRICA_GATE = "log_mae"


def metricas_de_produccion(
    client: MlflowClient, model_name: str = MODEL_NAME
) -> dict | None:
    """Metricas del run que respalda la version en Production, o None si no hay.

    Primer despliegue: el modelo registrado todavia no existe (algunos stores
    lo reportan como excepcion en vez de lista vacia) -> no hay champion.
    """
    try:
        versiones = client.get_latest_versions(model_name, stages=["Production"])
    except MlflowException as exc:
        if exc.error_code == "RESOURCE_DOES_NOT_EXIST":
            return None
        raise
    if not versiones:
        return None
    run = client.get_run(versiones[0].run_id)
    return dict(run.data.metrics)


def evaluar_gate(
    challenger: dict, champion: dict | None, metrica: str = METRICA_GATE
) -> bool:
    """Gate champion/challenger: True si corresponde promover a Production.

    Sin champion promueve (primer despliegue). El empate promueve: un refresh
    con datos nuevos y misma calidad debe pasar a servir.
    """
    if champion is None or metrica not in champion:
        return True
    return float(challenger[metrica]) <= float(champion[metrica])


def registrar_y_promover(
    client: MlflowClient, run_id: str, gate_paso: bool, model_name: str = MODEL_NAME
) -> tuple[int, str]:
    """Registra el modelo del run como version nueva y la transiciona.

    Siempre pasa por Staging (queda auditada aunque el gate retenga); si el
    gate paso, sigue a Production archivando la version anterior. Devuelve
    (version, stage_final).
    """
    import mlflow

    mv = mlflow.register_model(f"runs:/{run_id}/model", model_name)
    version = int(mv.version)
    client.transition_model_version_stage(model_name, version, stage="Staging")
    if not gate_paso:
        return version, "Staging"
    client.transition_model_version_stage(
        model_name, version, stage="Production", archive_existing_versions=True
    )
    return version, "Production"
