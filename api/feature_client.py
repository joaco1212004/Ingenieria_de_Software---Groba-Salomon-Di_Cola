"""Retrieval de features para la inferencia online (ADR-0020/0023).

El serving lee del MISMO feature mart que el training
(`gold.fct_features_declino`, ADR-0020): la serie mensual de tasa diaria de
petroleo del pozo. La consistencia train/serve es por construccion — no hay
un segundo camino de calculo de features que pueda divergir.

El contrato del endpoint identifica al pozo por `sigla` (dim_pozo), asi que
se mapea sigla -> idpozo natural con un join. La serie se reindexa a meses
calendario continuos (NaN en meses sin registro), igual que espera el
predictor de `pipeline/ml/m3.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pipeline.ml.config import M3Config

_UMBRALES = M3Config()  # min_months / min_nonzero: mismos que el training

_SERIES_QUERY = text(
    """
    SELECT f.idpozo, f.fecha_periodo, f.tasa_diaria_pet
    FROM gold.fct_features_declino f
    JOIN gold.dim_pozo dp ON dp.idpozo = f.idpozo
    WHERE dp.sigla = :sigla
    ORDER BY f.fecha_periodo
"""
)

_POZO_EXISTE_QUERY = text("SELECT 1 FROM gold.dim_pozo WHERE sigla = :sigla LIMIT 1")


class WellNotFound(Exception):
    """La sigla no existe en dim_pozo -> 404."""


class InsufficientHistory(Exception):
    """El pozo existe pero no tiene historia suficiente para el modelo -> 503."""


@dataclass
class WellSeries:
    pid: int
    q: np.ndarray  # tasa diaria mensual, NaN en meses sin registro
    primer_mes: pd.Period  # mes calendario de q[0]

    @property
    def ultimo_mes(self) -> pd.Period:
        return self.primer_mes + (len(self.q) - 1)


def get_well_series(engine: Engine, sigla: str) -> WellSeries:
    """Serie historica mensual continua del pozo, lista para el predictor."""
    with engine.connect() as conn:
        rows = conn.execute(_SERIES_QUERY, {"sigla": sigla}).mappings().all()
        if not rows:
            existe = conn.execute(_POZO_EXISTE_QUERY, {"sigla": sigla}).first()
            if existe is None:
                raise WellNotFound(f"pozo '{sigla}' inexistente")
            raise InsufficientHistory(
                f"pozo '{sigla}' sin historia en el feature mart "
                f"(cohorte: >= {_UMBRALES.min_months} meses con senal)"
            )

    df = pd.DataFrame(rows)
    df["fecha_periodo"] = pd.to_datetime(df["fecha_periodo"])
    df["mes"] = df["fecha_periodo"].dt.to_period("M")
    serie = df.groupby("mes", observed=True)["tasa_diaria_pet"].mean()

    # Reindexo a meses calendario continuos: los gaps quedan NaN (el modelo
    # los ignora via mask, no se imputan) — mismo criterio que el training.
    idx = pd.period_range(serie.index.min(), serie.index.max(), freq="M")
    q = serie.reindex(idx).to_numpy(dtype=float)

    if (
        len(q) < _UMBRALES.min_months
        or int(np.count_nonzero(q > 0)) < _UMBRALES.min_nonzero
    ):
        raise InsufficientHistory(
            f"pozo '{sigla}' con historia insuficiente: {len(q)} meses, "
            f"{int(np.count_nonzero(q > 0))} con produccion positiva "
            f"(minimos: {_UMBRALES.min_months} / {_UMBRALES.min_nonzero})"
        )

    return WellSeries(pid=int(df["idpozo"].iloc[0]), q=q, primer_mes=idx[0])
