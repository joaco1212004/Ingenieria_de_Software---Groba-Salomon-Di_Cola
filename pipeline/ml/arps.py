"""Decline Curve Analysis: curvas de Arps, deteccion de pico y mejor ajuste.

Port de src/arps.py del repo de investigacion, sin los extras de EUR de curva
ni los baselines que no usa M3. Implementa las tres curvas clasicas de Arps
(exponencial, armonica e hiperbolica), la deteccion del pico via changepoint
(ruptures, Dynp con 1 changepoint; fallback argmax) y la seleccion del mejor
ajuste por log-MAE. Ref.: Kongkiatpaiboon (2025), SPE-224468-MS.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import curve_fit

from pipeline.ml.evaluacion import log_mae


# --- Curvas de Arps --------------------------------------------------------


def arps_exponencial(t: np.ndarray, qi: float, di: float) -> np.ndarray:
    """b = 0:  q(t) = qi * exp(-di * t)"""
    return qi * np.exp(-di * t)


def arps_armonica(t: np.ndarray, qi: float, di: float) -> np.ndarray:
    """b = 1:  q(t) = qi / (1 + di * t)"""
    return qi / (1.0 + di * t)


def arps_hiperbolica(t: np.ndarray, qi: float, di: float, b: float) -> np.ndarray:
    """0 < b < 1:  q(t) = qi / (1 + b*di*t)^(1/b)"""
    return qi / np.power(1.0 + b * di * t, 1.0 / b)


def predict_dca(model: dict, t: np.ndarray) -> np.ndarray:
    """Evalua un modelo DCA ajustado (dict con kind, qi, di, b) en los tiempos `t`."""
    t = np.asarray(t, dtype=float)
    qi, di, b = model["qi"], model["di"], model.get("b", 0.0)
    if model["kind"] == "exponencial":
        return arps_exponencial(t, qi, di)
    if model["kind"] == "armonica":
        return arps_armonica(t, qi, di)
    return arps_hiperbolica(t, qi, di, b)


# --- Deteccion del pico (changepoint) --------------------------------------


def detect_peak(q: np.ndarray, use_changepoint: bool = True) -> int:
    """Indice del pico de produccion, desde donde arranca la fase de declino.

    Muchos pozos hacen choke-back inicial y no arrancan en su maximo el primer
    mes, asi que se localiza el pico antes de ajustar el DCA. Con
    `use_changepoint`, usa ruptures (Dynp, 1 changepoint) y toma el maximo del
    segmento de buildup; si falla, cae al argmax.
    """
    # NaN = mes sin medicion util (p. ej. tef = 0): no puede ser candidato a pico.
    q = np.nan_to_num(np.asarray(q, dtype=float), nan=0.0)
    if len(q) < 3:
        return 0
    if use_changepoint:
        try:
            import ruptures as rpt

            bkp = rpt.Dynp(model="l2", min_size=2, jump=1).fit(q).predict(n_bkps=1)[0]
            return int(np.argmax(q[: max(int(bkp), 1)]))
        except Exception:
            pass
    return int(np.argmax(q))


# --- Ajuste ----------------------------------------------------------------


def _safe_fit(fn, t, q, p0, bounds, maxfev: int = 5000):
    try:
        popt, _ = curve_fit(fn, t, q, p0=p0, bounds=bounds, maxfev=maxfev)
        return popt
    except Exception:
        return None


def fit_best_dca(t: np.ndarray, q: np.ndarray) -> dict | None:
    """Ajusta exp/armonica/hiperbolica y devuelve el mejor por log-MAE en muestra.

    Devuelve un dict con `kind`, `qi`, `di`, `b` y `train_log_mae`, o None si
    ningun ajuste converge.
    """
    t = np.asarray(t, dtype=float)
    q = np.asarray(q, dtype=float)
    if len(q) < 4:
        return None
    qi0 = float(np.max(q)) if np.max(q) > 0 else 1.0
    qi_hi = qi0 * 10.0 + 1.0

    candidatos: list[dict] = []

    p = _safe_fit(
        arps_exponencial, t, q, p0=[qi0, 0.05], bounds=([1e-6, 1e-9], [qi_hi, 5.0])
    )
    if p is not None:
        candidatos.append(
            {"kind": "exponencial", "qi": float(p[0]), "di": float(p[1]), "b": 0.0}
        )

    p = _safe_fit(
        arps_armonica, t, q, p0=[qi0, 0.05], bounds=([1e-6, 1e-9], [qi_hi, 5.0])
    )
    if p is not None:
        candidatos.append(
            {"kind": "armonica", "qi": float(p[0]), "di": float(p[1]), "b": 1.0}
        )

    p = _safe_fit(
        arps_hiperbolica,
        t,
        q,
        p0=[qi0, 0.05, 0.5],
        bounds=([1e-6, 1e-9, 1e-6], [qi_hi, 5.0, 2.0]),
    )
    if p is not None:
        candidatos.append(
            {
                "kind": "hiperbolica",
                "qi": float(p[0]),
                "di": float(p[1]),
                "b": float(p[2]),
            }
        )

    if not candidatos:
        return None

    for m in candidatos:
        m["train_log_mae"] = log_mae(q, predict_dca(m, t))
    return min(candidatos, key=lambda m: m["train_log_mae"])


class ArpsBaseline:
    """Mejor curva de Arps (exp/armonica/hiperbolica) tras detectar el pico.

    Baseline oficial de la industria (DCA). Se ajusta sobre la fase de declino
    del historial de entrenamiento y se extrapola usando indices de tiempo de
    la serie completa. En M3 pone la tendencia; la LSTM corrige el residual.
    """

    def __init__(self, use_changepoint: bool = True) -> None:
        self.use_changepoint = use_changepoint
        self.peak: int = 0
        self.model: dict | None = None

    def fit(self, q_train: np.ndarray) -> "ArpsBaseline":
        q_train = np.asarray(q_train, dtype=float)
        self.peak = detect_peak(q_train, self.use_changepoint)
        decline = q_train[self.peak :]
        # el ajuste usa solo meses observados, conservando sus indices de tiempo
        t = np.arange(len(decline), dtype=float)
        valid = np.isfinite(decline)
        self.model = fit_best_dca(t[valid], decline[valid])
        return self

    @property
    def fitted(self) -> bool:
        return self.model is not None

    def predict(self, t_global: np.ndarray) -> np.ndarray:
        """Predice en indices de tiempo de la serie completa (>= len(q_train) para test)."""
        t_global = np.atleast_1d(np.asarray(t_global, dtype=float))
        if self.model is None:
            return np.full(len(t_global), np.nan)
        return predict_dca(self.model, t_global - self.peak)
