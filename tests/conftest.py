"""Setea una API key de testing antes de que pytest importe los módulos.

Si el entorno (CI, dev local) no provee API_KEY, se usa este valor solo para
que los tests puedan correr. No es la key real ni la de la adenda — es un
placeholder local de tests.
"""

import os

if not os.environ.get("API_KEY"):
    os.environ["API_KEY"] = "pytest-only-key-not-real"
