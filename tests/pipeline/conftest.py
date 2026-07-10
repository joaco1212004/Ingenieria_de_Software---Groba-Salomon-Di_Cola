"""Fixtures compartidas de los tests de ML: cohorte sintetica de declino.

Pozos con declino exponencial + ruido lognormal + algunos NaN (meses sin
operar), suficientes para el split 60/20/20 temporal y a nivel pozo. Largos
variados para ejercitar la estratificacion por cuartil.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def generar_df_declino(n_pozos: int = 14, seed: int = 0) -> pd.DataFrame:
    """DataFrame con el shape del feature mart (idpozo, fecha_periodo, tasa_diaria_pet)."""
    rng = np.random.default_rng(seed)
    filas = []
    for pid in range(1, n_pozos + 1):
        n = int(rng.integers(30, 60))
        qi = float(rng.uniform(50, 200))
        di = float(rng.uniform(0.03, 0.1))
        t = np.arange(n)
        q = qi * np.exp(-di * t) * rng.lognormal(0.0, 0.1, n)
        q[rng.integers(0, n, size=2)] = np.nan  # meses sin operar (tef<=0)
        fechas = pd.date_range("2020-01-31", periods=n, freq="ME")
        for i in range(n):
            filas.append(
                {
                    "idpozo": pid,
                    "fecha_periodo": fechas[i],
                    "tasa_diaria_pet": q[i],
                }
            )
    return pd.DataFrame(filas)


@pytest.fixture
def df_declino() -> pd.DataFrame:
    return generar_df_declino()
