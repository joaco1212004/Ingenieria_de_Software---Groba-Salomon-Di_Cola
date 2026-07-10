"""Configuracion del entrenamiento M3: hiperparametros ganadores fijos.

Reemplaza al `config.yaml` + `mejores_hiperparametros.yaml` del repo de
investigacion: aca hay un solo modelo con la config ganadora del sweep
(seleccion por perdida de validacion, lambda=0.5), asi que alcanza con
constantes. Todos los campos se loggean como params del run de MLflow
(reproducibilidad: params + semilla por run, ADR-0019).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class M3Config:
    # Senal objetivo: tasa diaria (prod_pet / tef), la senal robusta al downtime
    # segun el informe (la calculan dbt en gold.fct_features_declino).
    target: str = "tasa_diaria_pet"

    # Hiperparametros ganadores del sweep para petroleo (mejores_hiperparametros.yaml).
    hidden: int = 64
    lr: float = 5e-4
    dropout: float = 0.0
    horizonte: int = 60
    epochs: int = 300
    paciencia: int = 25
    seed: int = 42
    use_changepoint: bool = True

    # Cohorte y splits (mismos umbrales que el benchmark).
    min_months: int = 12
    min_nonzero: int = 6
    min_val: int = 3
    min_test: int = 3
    meses_sin_reportar: int = 12

    # Tope de pozos para smoke runs o instancias chicas (None = sin tope).
    max_wells: int | None = None


def config_from_env() -> M3Config:
    """Config con overrides por env: ML_EPOCHS y ML_MAX_WELLS.

    Pensado para smoke runs locales y para achicar el entrenamiento en la EC2
    chica sin tocar codigo.
    """
    overrides: dict = {}
    if os.getenv("ML_EPOCHS"):
        overrides["epochs"] = int(os.environ["ML_EPOCHS"])
    if os.getenv("ML_MAX_WELLS"):
        overrides["max_wells"] = int(os.environ["ML_MAX_WELLS"])
    return M3Config(**overrides)
