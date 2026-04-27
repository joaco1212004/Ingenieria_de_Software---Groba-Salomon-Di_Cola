import os

from fastapi import Header, HTTPException, status

# La API key vive solo en el entorno (.env del host, GitHub Secret en CI).
# No hay default: si la variable no está seteada, la app no arranca.
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise RuntimeError(
        "API_KEY environment variable is required. Set it in .env or export it."
    )


def verify_api_key(x_api_key: str = Header(default=None, alias="X-API-Key")):
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Invalid API Key"
        )
