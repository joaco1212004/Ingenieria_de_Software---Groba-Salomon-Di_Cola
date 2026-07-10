"""Metricas de evaluacion del modelo de declino (port de src/evaluacion.py).

Metricas de forecasting del benchmark: log-MAE como metrica primaria (robusta a
outliers, maneja ceros via log1p), RMSE, error del acumulado de test (proxy de
EUR truncado) y el error de EUR real sobre pozos cerrados (GOLD). Los resultados
por pozo van a MLflow como medianas; no hay persistencia local.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# --- Metricas ---------------------------------------------------------------


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def log_mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """MAE sobre log1p de la produccion.

    Metrica primaria del metodo de referencia (Kongkiatpaiboon 2025): menos
    sensible a outliers que el MAE crudo y maneja ceros via log1p. Los negativos
    se recortan a 0 (una tasa negativa no tiene sentido fisico).
    """
    yt = np.log1p(np.clip(np.asarray(y_true, dtype=float), 0.0, None))
    yp = np.log1p(np.clip(np.asarray(y_pred, dtype=float), 0.0, None))
    return float(np.mean(np.abs(yt - yp)))


def error_acum_rel(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Error relativo del acumulado en el horizonte dado. NO es EUR: es un proxy
    sobre la ventana evaluada. Aritmetica generica reusada por el acumulado de
    test y por el acumulado real de pozos cerrados (GOLD)."""
    total_true = float(np.nansum(y_true))
    if total_true == 0.0:
        return float("nan")
    return float(abs(float(np.nansum(y_pred)) - total_true) / total_true)


def r2_eur(df_res: pd.DataFrame, log: bool = False) -> float:
    """R2 de la EUR real vs predicha sobre pozos cerrados (GOLD).

    Con log=True usa log1p(EUR): coherente con log-MAE, robusto a la cola
    pesada. No acotado a [0,1]: tope 1, puede ser negativo. NaN si hay menos de
    2 pozos o la varianza real es nula.
    """
    cols = ["eur_true_gold", "eur_pred_gold"]
    if not all(c in df_res for c in cols):
        return float("nan")
    d = df_res.dropna(subset=cols)
    if len(d) < 2:
        return float("nan")
    yt = d["eur_true_gold"].to_numpy(dtype=float)
    yp = d["eur_pred_gold"].to_numpy(dtype=float)
    if log:
        yt = np.log1p(np.clip(yt, 0.0, None))
        yp = np.log1p(np.clip(yp, 0.0, None))
    ss_res = float(np.sum((yt - yp) ** 2))
    ss_tot = float(np.sum((yt - yt.mean()) ** 2))
    return float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


# --- Evaluacion por pozo ------------------------------------------------------


def evaluar_en_fold(
    cohorte: dict, predecir, pozos, con_cierre: bool = True
) -> list[dict]:
    """Evalua un modelo sobre un conjunto de pozos, en su ventana temporal de
    test (ultimo 20%).

    `predecir(pid, q, k_tr, k_va, t)` debe devolver la prediccion para los
    indices de tiempo globales `t` (todos >= k_tr), usando SOLO `q[:k_tr]` como
    historia (sin fuga), o None si el modelo no puede predecir ese pozo.

    Con `con_cierre=True`, para los pozos CERRADOS agrega `err_eur_gold`: el
    error del acumulado sobre TODO lo restante (val+test), que para un pozo
    cerrado es su EUR real (no truncada).
    """
    filas: list[dict] = []
    for pid in sorted(pozos):
        q = cohorte["series"][pid]
        k_tr, k_va = cohorte["cortes"][pid]
        n = len(q)

        t_test = np.arange(k_va, n, dtype=float)
        pred = predecir(pid, q, k_tr, k_va, t_test)
        if pred is None:
            continue
        pred = np.asarray(pred, dtype=float)
        v = np.isfinite(q[k_va:])
        if int(v.sum()) < 1 or not np.all(np.isfinite(pred[v])):
            continue
        fila = {
            "idpozo": pid,
            "log_mae": log_mae(q[k_va:][v], pred[v]),
            "rmse": rmse(q[k_va:][v], pred[v]),
            "err_acum_test": error_acum_rel(q[k_va:][v], pred[v]),
        }

        if con_cierre and pid in cohorte["cerrados"]:
            t_resto = np.arange(k_tr, n, dtype=float)
            pr = predecir(pid, q, k_tr, k_va, t_resto)
            if pr is not None:
                pr = np.asarray(pr, dtype=float)
                vr = np.isfinite(q[k_tr:])
                if int(vr.sum()) >= 1 and np.all(np.isfinite(pr[vr])):
                    fila["err_eur_gold"] = error_acum_rel(q[k_tr:][vr], pr[vr])
                    fila["eur_true_gold"] = float(np.nansum(q[k_tr:][vr]))
                    fila["eur_pred_gold"] = float(np.nansum(pr[vr]))
        filas.append(fila)
    return filas


def evaluar_en_test(cohorte: dict, predecir) -> list[dict]:
    """Evalua sobre los POZOS DE TEST (fold a nivel pozo)."""
    return evaluar_en_fold(cohorte, predecir, cohorte["folds"]["test"], con_cierre=True)


def resumen_modelo(df_res: pd.DataFrame) -> dict[str, float]:
    """Medianas por pozo de las metricas estandar (+ GOLD de cierre si esta)."""
    res = {
        "pozos": int(len(df_res)),
        "log_mae": float(df_res["log_mae"].median()),
        "rmse": float(df_res["rmse"].median()),
        "err_acum_test": float(df_res["err_acum_test"].median()),
    }
    if "err_eur_gold" in df_res and df_res["err_eur_gold"].notna().any():
        gold = df_res["err_eur_gold"].dropna()
        res["err_eur_gold"] = float(gold.median())
        res["pozos_cerrados"] = int(len(gold))
        res["r2_eur"] = r2_eur(df_res)
        res["r2_log_eur"] = r2_eur(df_res, log=True)
    return res
