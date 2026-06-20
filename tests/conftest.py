"""Setea una API key de testing antes de que pytest importe los módulos.

Si el entorno (CI, dev local) no provee API_KEY, se usa este valor solo para
que los tests puedan correr. No es la key real ni la de la adenda — es un
placeholder local de tests.
"""

import os
from unittest.mock import MagicMock

import pytest

if not os.environ.get("API_KEY"):
    os.environ["API_KEY"] = "pytest-only-key-not-real"

from api.db import get_engine  # noqa: E402 — importar después de setear API_KEY
from api.main import api  # noqa: E402


@pytest.fixture(autouse=True)
def mock_db():
    mock = MagicMock()
    api.dependency_overrides[get_engine] = lambda: mock
    yield mock
    api.dependency_overrides.clear()
