"""Carga y cache del modelo de serving desde el Model Registry (ADR-0023).

La API sirve siempre la version en stage Production del modelo registrado por
el pipeline de training (ADR-0019/0022). El artefacto del run trae dos piezas:
la LSTM (flavor pytorch) y un `config.json` con lo necesario para reconstruir
el predictor (`hacer_predecir_m3` re-ajusta Arps por pozo en cada inferencia).

Cache con TTL: la carga del registry es cara (descarga de artefactos), asi que
se cachea el predictor y cada `_TTL_SEGUNDOS` se consulta el registry; si hay
una version nueva en Production (un retrain que paso el gate) se recarga sin
reiniciar la API. Si MLflow esta caido pero hay un modelo cacheado, se sigue
sirviendo el cache (degradacion suave); sin cache, `ModelUnavailable` -> 503.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)

_TTL_SEGUNDOS = 300


class ModelUnavailable(Exception):
    """No hay modelo en Production o el registry no responde (sin cache)."""


@dataclass
class LoadedModel:
    predictor: Callable  # contrato: predecir(pid, q, k_tr, k_va, t) -> tasas | None
    version: int
    horizonte: int
    loaded_at: float


_cache: LoadedModel | None = None
_lock = threading.Lock()


def _production_version(client, model_name: str) -> int | None:
    """Version actual en Production o None si no hay (primer despliegue)."""
    from mlflow.exceptions import MlflowException

    try:
        versiones = client.get_latest_versions(model_name, stages=["Production"])
    except MlflowException as exc:
        if exc.error_code == "RESOURCE_DOES_NOT_EXIST":
            return None
        raise
    if not versiones:
        return None
    return int(versiones[0].version)


def _load_production() -> LoadedModel:
    """Carga el modelo Production + config.json y arma el predictor."""
    import mlflow
    from mlflow.tracking import MlflowClient

    from pipeline.ml.m3 import hacer_predecir_m3
    from pipeline.ml.registry import MODEL_NAME

    client = MlflowClient()
    version = _production_version(client, MODEL_NAME)
    if version is None:
        raise ModelUnavailable(
            f"no hay version en Production del modelo '{MODEL_NAME}'"
        )

    mv = client.get_model_version(MODEL_NAME, str(version))
    model = mlflow.pytorch.load_model(f"models:/{MODEL_NAME}/Production")
    config_path = mlflow.artifacts.download_artifacts(
        run_id=mv.run_id, artifact_path="config.json"
    )
    with open(config_path, encoding="utf-8") as fh:
        cfg = json.load(fh)

    predictor = hacer_predecir_m3(model, cfg["horizonte"], cfg["use_changepoint"])
    logger.info("modelo %s v%s (Production) cargado", MODEL_NAME, version)
    return LoadedModel(
        predictor=predictor,
        version=version,
        horizonte=int(cfg["horizonte"]),
        loaded_at=time.monotonic(),
    )


def get_model() -> LoadedModel:
    """Predictor cacheado; refresca del registry cuando el TTL vence.

    - Cache fresco -> se devuelve directo (camino caliente, sin red).
    - TTL vencido -> consulta el registry; si Production cambio de version,
      recarga; si el registry falla pero hay cache, sirve el cache.
    - Sin cache y sin registry/Production -> ModelUnavailable (la ruta lo
      traduce a HTTP 503).
    """
    global _cache
    with _lock:
        if _cache is not None and time.monotonic() - _cache.loaded_at < _TTL_SEGUNDOS:
            return _cache
        try:
            if _cache is not None:
                from mlflow.tracking import MlflowClient

                from pipeline.ml.registry import MODEL_NAME

                actual = _production_version(MlflowClient(), MODEL_NAME)
                if actual == _cache.version:
                    _cache.loaded_at = time.monotonic()
                    return _cache
            _cache = _load_production()
            _actualizar_metrica_version(_cache.version)
            return _cache
        except ModelUnavailable:
            _cache = None
            raise
        except Exception as exc:  # registry caido, artefactos inaccesibles, etc.
            if _cache is not None:
                logger.warning(
                    "registry inaccesible, sirvo cache v%s: %s", _cache.version, exc
                )
                _cache.loaded_at = time.monotonic()
                return _cache
            raise ModelUnavailable(f"registry de modelos inaccesible: {exc}") from exc


def reset_cache() -> None:
    """Invalida el cache (tests y operaciones)."""
    global _cache
    with _lock:
        _cache = None


def _actualizar_metrica_version(version: int) -> None:
    from api.metrics import MODEL_VERSION

    MODEL_VERSION.set(version)
