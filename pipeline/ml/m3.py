"""M3: hibrido Arps + LSTM sobre el residual log (port del modelo ganador).

La tendencia la pone Arps ajustado al train de CADA pozo; una LSTM GLOBAL
(aprende de los pozos del fold de train) lee la secuencia de residuales log
del train (lo que Arps no explico mes a mes) mas los parametros del ajuste, y
predice la correccion para los proximos `horizonte` meses (multi-step directo,
sin autoregresion). Prediccion final:

    q_hat(t) = expm1( log1p(arps(t)) + correccion(t - k_tr) )

Mas alla del horizonte, la ultima correccion se repite. Todo corre en CPU
(la EC2 no tiene GPU y el modelo es chico).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.nn.utils.rnn import pack_padded_sequence

from pipeline.ml.arps import ArpsBaseline
from pipeline.ml.config import M3Config
from pipeline.ml.datos import set_seed
from pipeline.ml.evaluacion import evaluar_en_test, resumen_modelo
from pipeline.ml.redes import entrenar, masked_mse, pad_secuencias

_KINDS = ("exponencial", "armonica", "hiperbolica")
N_ESTATICO = 8  # 5 features del ajuste + one-hot de 3 tipos de curva


def preparar_pozo(q: np.ndarray, k_tr: int, horizonte: int, use_cp: bool):
    """Ajuste de Arps + secuencia de residuales de train + target del horizonte.

    Devuelve (arps, seq (L,3), estatico (8,), y (H,), mask (H,)) o None si no
    ajusta. seq: [residual log, log1p(base), observado] para los meses
    post-pico del train.
    """
    arps = ArpsBaseline(use_cp).fit(q[:k_tr])
    if not arps.fitted:
        return None
    t_train = np.arange(arps.peak, k_tr, dtype=float)
    if len(t_train) < 4:
        return None
    base_tr = np.clip(arps.predict(t_train), 0.0, None)
    q_tr = q[arps.peak : k_tr]
    obs_tr = np.isfinite(q_tr)
    resid = np.where(
        obs_tr,
        np.log1p(np.clip(np.nan_to_num(q_tr), 0.0, None)) - np.log1p(base_tr),
        0.0,
    )
    seq = np.column_stack([resid, np.log1p(base_tr), obs_tr.astype(float)])

    m = arps.model
    estatico = np.array(
        [
            np.log(max(m["qi"], 1e-6)),
            np.log(max(m["di"], 1e-9)),
            m["b"],
            m.get("train_log_mae", 0.0),
            float(k_tr - arps.peak),
        ]
        + [1.0 if m["kind"] == k else 0.0 for k in _KINDS]
    )

    # target: residual real de los proximos H meses (val+test del pozo), enmascarado
    n = len(q)
    h_real = min(n - k_tr, horizonte)
    t_fut = np.arange(k_tr, k_tr + h_real, dtype=float)
    base_fut = np.clip(arps.predict(t_fut), 0.0, None)
    q_fut = q[k_tr : k_tr + h_real]
    obs_fut = np.isfinite(q_fut)
    y = np.zeros(horizonte)
    mask = np.zeros(horizonte)
    y[:h_real] = np.where(
        obs_fut,
        np.log1p(np.clip(np.nan_to_num(q_fut), 0.0, None)) - np.log1p(base_fut),
        0.0,
    )
    mask[:h_real] = obs_fut.astype(float)
    return arps, seq, estatico, y, mask


class LSTMResidual(nn.Module):
    def __init__(
        self,
        hidden: int,
        n_estatico: int,
        horizonte: int,
        capas: int = 1,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            3,
            hidden,
            num_layers=capas,
            batch_first=True,
            dropout=dropout if capas > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden + n_estatico, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, horizonte),
        )

    def forward(
        self, x: torch.Tensor, largos: torch.Tensor, estatico: torch.Tensor
    ) -> torch.Tensor:
        packed = pack_padded_sequence(
            x, largos.cpu(), batch_first=True, enforce_sorted=False
        )
        _, (h, _) = self.lstm(packed)
        return self.head(torch.cat([h[-1], estatico], dim=1))


def armar_fold(
    series: dict[int, np.ndarray],
    cortes: dict[int, tuple[int, int]],
    pozos,
    horizonte: int,
    use_cp: bool,
):
    """Tensores de un fold: (x, largos, estatico, y, mask). None si quedo vacio."""
    seqs, est, ys, masks = [], [], [], []
    for pid in sorted(pozos):
        r = preparar_pozo(series[pid], cortes[pid][0], horizonte, use_cp)
        if r is None:
            continue
        _, seq, e, y, m = r
        seqs.append(seq)
        est.append(e)
        ys.append(y)
        masks.append(m)
    if not seqs:
        return None
    x, largos = pad_secuencias(seqs)
    return (
        x,
        largos,
        torch.tensor(np.asarray(est), dtype=torch.float32),
        torch.tensor(np.asarray(ys), dtype=torch.float32),
        torch.tensor(np.asarray(masks), dtype=torch.float32),
    )


def hacer_predecir_m3(model: LSTMResidual, horizonte: int, use_cp: bool):
    """Cierra el predictor con el contrato `predecir(pid, q, k_tr, k_va, t)`.

    Stateless respecto de los datos de entrenamiento: re-ajusta Arps al train
    del pozo evaluado y le suma la correccion de la LSTM.
    """

    def predecir(pid, q, k_tr, k_va, t):
        r = preparar_pozo(q, k_tr, horizonte, use_cp)
        if r is None:
            return None
        arps_fit, seq, e, _, _ = r
        model.eval()
        with torch.no_grad():
            x, largos = pad_secuencias([seq])
            eb = torch.tensor(e[None, :], dtype=torch.float32)
            r_hat = model(x, largos, eb)[0].numpy()
        t = np.asarray(t, dtype=float)
        base = np.clip(arps_fit.predict(t), 0.0, None)
        # offset dentro del horizonte; mas alla se repite la ultima correccion
        off = np.minimum((t - k_tr).astype(int), horizonte - 1)
        return np.expm1(np.clip(np.log1p(base) + r_hat[off], 0.0, None))

    return predecir


def entrenar_m3(cohorte: dict, cfg: M3Config, log_fn=None):
    """Entrena M3 sobre el cohorte y lo evalua en los pozos de test.

    Devuelve (model, info, resumen, filas): la red entrenada (mejor estado
    restaurado), el detalle del loop (`mejor_val`, `epocas`, `historia`), las
    medianas de test (`resumen_modelo`) y las metricas por pozo.

    Lanza ValueError si algun fold queda vacio (cohorte insuficiente).
    """
    set_seed(cfg.seed)
    series, cortes, folds = cohorte["series"], cohorte["cortes"], cohorte["folds"]

    tr = armar_fold(series, cortes, folds["train"], cfg.horizonte, cfg.use_changepoint)
    va = armar_fold(series, cortes, folds["val"], cfg.horizonte, cfg.use_changepoint)
    if tr is None or va is None:
        raise ValueError(
            "cohorte insuficiente: fold de train o val sin pozos con ajuste de Arps"
        )
    x_tr, l_tr, e_tr, y_tr, m_tr = tr
    x_va, l_va, e_va, y_va, m_va = va

    # misma semilla justo antes de construir el modelo (pesos reproducibles)
    torch.manual_seed(cfg.seed)
    model = LSTMResidual(cfg.hidden, N_ESTATICO, cfg.horizonte, dropout=cfg.dropout)

    info = entrenar(
        model,
        loss_train=lambda: masked_mse(model(x_tr, l_tr, e_tr), y_tr, m_tr),
        loss_val=lambda: masked_mse(model(x_va, l_va, e_va), y_va, m_va).item(),
        epochs=cfg.epochs,
        lr=cfg.lr,
        paciencia=cfg.paciencia,
        log_fn=log_fn,
    )
    model.eval()

    filas = evaluar_en_test(
        cohorte, hacer_predecir_m3(model, cfg.horizonte, cfg.use_changepoint)
    )
    if not filas:
        raise ValueError("cohorte insuficiente: ningun pozo de test evaluable")
    resumen = resumen_modelo(pd.DataFrame(filas))
    return model, info, resumen, filas
