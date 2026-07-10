"""Cohorte de entrenamiento: series por pozo y splits (port de src/datos.py).

Adaptado a este stack: la entrada es un DataFrame que sale del feature mart
gold (`fct_features_declino`, columnas idpozo / fecha_periodo / tasa_diaria_pet)
en vez de un parquet local, y la tasa diaria ya viene calculada por dbt (tef<=0
-> NULL, nunca 0). Se conservan las reglas metodologicas del benchmark:

- Series mensuales por pozo con filtros de historia y senal (doble guarda del
  filtro que ya aplica el feature mart).
- Split TEMPORAL 60/20/20 por pozo (train para ajustar, val para early stop,
  test = ultimo 20% para el reporte).
- Split A NIVEL POZO 60/20/20 aleatorio estratificado por longitud: el modelo
  es global y se evalua solo en pozos que jamas vio.
- Pozos cerrados (sin reportar hace >= N meses): su acumulado observado es la
  EUR real -> subconjunto GOLD para el error de EUR.
"""

from __future__ import annotations

import random
from typing import Iterator

import numpy as np
import pandas as pd

from pipeline.ml.config import M3Config


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def iter_well_series(
    df: pd.DataFrame,
    target: str = "tasa_diaria_pet",
    time_col: str = "fecha_periodo",
    id_col: str = "idpozo",
    min_months: int = 12,
    min_nonzero: int = 6,
) -> Iterator[tuple[int, np.ndarray]]:
    """Genera `(idpozo, q)` por pozo, ordenado en el tiempo.

    Filtra pozos con menos de `min_months` registros o con menos de
    `min_nonzero` meses de produccion positiva. `q` puede contener NaN (meses
    sin medicion util, tef<=0): los modelos deben ignorarlos, no imputarlos.
    """
    for pid, g in df.sort_values(time_col).groupby(id_col, observed=True):
        q = g[target].to_numpy(dtype=float)
        if len(q) >= min_months and int(np.count_nonzero(q > 0)) >= min_nonzero:
            yield int(pid), q


def split_temporal_602020(
    n: int,
    min_val: int = 3,
    min_test: int = 3,
    train_frac: float = 0.6,
    val_frac: float = 0.2,
) -> tuple[int, int] | None:
    """Cortes del split temporal por pozo: train = [:k_tr], val = [k_tr:k_va],
    test = [k_va:]. None si el pozo no alcanza para los tres tramos.
    """
    k_tr = int(round(n * train_frac))
    k_va = int(round(n * (train_frac + val_frac)))
    if k_tr < 6 or (k_va - k_tr) < min_val or (n - k_va) < min_test:
        return None
    return k_tr, k_va


def split_pozos(
    longitudes: dict[int, int],
    seed: int,
    fracs: tuple[float, float, float] = (0.6, 0.2, 0.2),
) -> dict[str, set[int]]:
    """Split A NIVEL POZO aleatorio, estratificado por cuartil de longitud.

    Aleatorio (no por longevidad): ordenar por antiguedad meteria en test una
    poblacion de otra epoca/tecnologia y la metrica mediria covariate shift, no
    generalizacion. La estratificacion solo equilibra las longitudes entre folds.
    """
    rng = np.random.default_rng(seed)
    ids = np.array(sorted(longitudes))
    n_meses = np.array([longitudes[p] for p in ids])
    cuartil = np.searchsorted(np.quantile(n_meses, [0.25, 0.5, 0.75]), n_meses)

    out: dict[str, set[int]] = {"train": set(), "val": set(), "test": set()}
    for c in range(4):
        grupo = rng.permutation(ids[cuartil == c])
        n_tr = int(round(fracs[0] * len(grupo)))
        n_va = int(round((fracs[0] + fracs[1]) * len(grupo)))
        out["train"].update(int(p) for p in grupo[:n_tr])
        out["val"].update(int(p) for p in grupo[n_tr:n_va])
        out["test"].update(int(p) for p in grupo[n_va:])
    return out


def pozos_cerrados(
    df: pd.DataFrame, meses_sin_reportar: int = 12, time_col: str = "fecha_periodo"
) -> set[int]:
    """Pozos cuyo ultimo registro es >= N meses anterior al fin del dataset.

    Para ellos la produccion acumulada observada ES la EUR real (ya no
    producen). El umbral evita confundir cierre con una parada temporal.
    """
    ult = df.groupby("idpozo", observed=True)[time_col].max()
    corte = df[time_col].max() - pd.DateOffset(months=meses_sin_reportar)
    return {int(p) for p in ult[ult < corte].index}


def preparar_cohorte(df: pd.DataFrame, cfg: M3Config) -> dict:
    """Arma todo lo que el entrenamiento necesita, con una sola pasada.

    `df` viene del feature mart (idpozo, fecha_periodo, tasa_diaria_pet).
    Devuelve dict con: `series` (pid -> q), `cortes` (pid -> (k_tr, k_va)),
    `folds` (train/val/test a nivel pozo), `cerrados` (set) y `target`.
    """
    df = df.copy()
    df["fecha_periodo"] = pd.to_datetime(df["fecha_periodo"])

    series: dict[int, np.ndarray] = {}
    cortes: dict[int, tuple[int, int]] = {}
    for pid, q in iter_well_series(
        df, target=cfg.target, min_months=cfg.min_months, min_nonzero=cfg.min_nonzero
    ):
        c = split_temporal_602020(len(q), min_val=cfg.min_val, min_test=cfg.min_test)
        if c is None:
            continue
        series[pid] = q
        cortes[pid] = c
        if cfg.max_wells is not None and len(series) >= cfg.max_wells:
            break

    folds = split_pozos({p: len(q) for p, q in series.items()}, seed=cfg.seed)
    cerrados = pozos_cerrados(df, cfg.meses_sin_reportar)
    return {
        "series": series,
        "cortes": cortes,
        "folds": folds,
        "cerrados": cerrados,
        "target": cfg.target,
    }
