"""Bloques de PyTorch del entrenamiento M3 (port de src/redes.py).

- `masked_mse`: perdida que ignora posiciones sin dato (padding o meses NaN).
- `pad_secuencias`: lleva una lista de secuencias de largo variable a un batch
  (B, L_max, F) + largos, para usar con `pack_padded_sequence`.
- `entrenar`: loop de entrenamiento full-batch con early stopping por validacion.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import torch


def masked_mse(
    pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor
) -> torch.Tensor:
    """MSE promediado solo sobre las posiciones observadas (mask = 1)."""
    se = (pred - target) ** 2 * mask
    return se.sum() / mask.sum().clamp(min=1.0)


def pad_secuencias(seqs: list[np.ndarray]) -> tuple[torch.Tensor, torch.Tensor]:
    """Apila secuencias (L_i, F) de largo variable en (B, L_max, F) + largos.

    El padding va al final con ceros; `largos` permite empaquetar con
    `torch.nn.utils.rnn.pack_padded_sequence(..., enforce_sorted=False)` para
    que la RNN procese solo los pasos reales.
    """
    largos = torch.tensor([len(s) for s in seqs], dtype=torch.long)
    l_max = int(largos.max())
    n_feat = seqs[0].shape[1]
    out = torch.zeros(len(seqs), l_max, n_feat, dtype=torch.float32)
    for i, s in enumerate(seqs):
        out[i, : len(s)] = torch.tensor(s, dtype=torch.float32)
    return out, largos


def entrenar(
    model: torch.nn.Module,
    loss_train: Callable[[], torch.Tensor],
    loss_val: Callable[[], float],
    epochs: int,
    lr: float,
    paciencia: int = 15,
    log_fn: Callable[[dict], None] | None = None,
) -> dict:
    """Loop de entrenamiento full-batch con early stopping por perdida de validacion.

    `loss_train()` computa la perdida de entrenamiento (con grad); `loss_val()`
    la de validacion (sin grad, float). Devuelve el mejor estado (se restaura en
    el modelo). `log_fn` recibe {"epoch", "train/loss", "val/loss"} por epoca
    (ahi se enchufa el logging a MLflow).
    """
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    mejor_val, mejor_estado, sin_mejora = float("inf"), None, 0
    historia = []
    for epoca in range(1, epochs + 1):
        model.train()
        opt.zero_grad()
        loss = loss_train()
        loss.backward()
        opt.step()

        model.eval()
        with torch.no_grad():
            val = float(loss_val())
        registro = {"epoch": epoca, "train/loss": float(loss.item()), "val/loss": val}
        historia.append(registro)
        if log_fn is not None:
            log_fn(registro)

        if val < mejor_val - 1e-6:
            mejor_val, sin_mejora = val, 0
            mejor_estado = {
                k: v.detach().clone() for k, v in model.state_dict().items()
            }
        else:
            sin_mejora += 1
            if sin_mejora >= paciencia:
                break

    if mejor_estado is not None:
        model.load_state_dict(mejor_estado)
    return {"mejor_val": mejor_val, "epocas": len(historia), "historia": historia}
