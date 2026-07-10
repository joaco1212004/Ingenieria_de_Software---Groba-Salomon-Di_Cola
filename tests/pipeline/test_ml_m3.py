"""Tests de la libreria pipeline/ml (sin Dagster ni servidor MLflow)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.ml.arps import detect_peak, fit_best_dca
from pipeline.ml.config import M3Config, config_from_env
from pipeline.ml.datos import preparar_cohorte, split_pozos
from pipeline.ml.m3 import N_ESTATICO, entrenar_m3, preparar_pozo
from pipeline.ml.registry import evaluar_gate

CFG_SMOKE = M3Config(epochs=3, hidden=8)


def test_fit_best_dca_recupera_declino_exponencial():
    t = np.arange(30, dtype=float)
    q = 100.0 * np.exp(-0.05 * t)
    m = fit_best_dca(t, q)
    assert m is not None
    np.testing.assert_allclose(m["qi"], 100.0, rtol=0.05)
    np.testing.assert_allclose(m["di"], 0.05, rtol=0.1)
    assert m["train_log_mae"] < 0.05


def test_detect_peak_encuentra_choke_back():
    # buildup de 5 meses (choke-back) y despues declino: el pico no es el mes 0
    q = np.concatenate([np.linspace(10, 100, 6), 100 * np.exp(-0.1 * np.arange(24))])
    assert detect_peak(q, use_changepoint=True) == 5
    assert detect_peak(q, use_changepoint=False) == 5  # argmax coincide aca


def test_preparar_pozo_shapes():
    t = np.arange(40, dtype=float)
    q = 100.0 * np.exp(-0.05 * t)
    r = preparar_pozo(q, k_tr=24, horizonte=60, use_cp=False)
    assert r is not None
    _, seq, estatico, y, mask = r
    assert seq.shape[1] == 3
    assert estatico.shape == (N_ESTATICO,)
    assert y.shape == (60,)
    assert mask.shape == (60,)
    # solo los meses reales del futuro (40-24=16) estan observados
    assert mask.sum() == 16


def test_split_pozos_determinista_con_seed():
    longitudes = {pid: 20 + pid for pid in range(1, 41)}
    a = split_pozos(longitudes, seed=42)
    b = split_pozos(longitudes, seed=42)
    assert a == b
    todos = a["train"] | a["val"] | a["test"]
    assert todos == set(longitudes)
    assert not (a["train"] & a["test"])


def test_preparar_cohorte_filtra_min_meses(df_declino):
    # un pozo con 5 meses no alcanza la historia minima (12)
    corto = df_declino[df_declino["idpozo"] == 1].head(5).assign(idpozo=999)
    df = pd.concat([df_declino, corto])
    cohorte = preparar_cohorte(df, CFG_SMOKE)
    assert 999 not in cohorte["series"]
    assert len(cohorte["series"]) == 14


def test_entrenar_m3_smoke(df_declino):
    cohorte = preparar_cohorte(df_declino, CFG_SMOKE)
    model, info, resumen, filas = entrenar_m3(cohorte, CFG_SMOKE)
    assert info["epocas"] <= 3
    assert np.isfinite(resumen["log_mae"])
    assert resumen["pozos"] == len(filas) > 0


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("ML_EPOCHS", "5")
    monkeypatch.setenv("ML_MAX_WELLS", "10")
    cfg = config_from_env()
    assert cfg.epochs == 5
    assert cfg.max_wells == 10
    assert cfg.seed == 42  # el resto no cambia


def test_evaluar_gate():
    assert evaluar_gate({"log_mae": 0.5}, None) is True  # primer despliegue
    assert evaluar_gate({"log_mae": 0.4}, {"log_mae": 0.5}) is True  # mejora
    assert evaluar_gate({"log_mae": 0.6}, {"log_mae": 0.5}) is False  # empeora
    assert evaluar_gate({"log_mae": 0.5}, {"log_mae": 0.5}) is True  # empate promueve
