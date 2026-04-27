import os

from fastapi import Header, HTTPException, status

# Default = valor preconfigurado en la adenda Fase 1. En producción se override
# con la variable de entorno API_KEY (.env de la EC2, no commiteado).
API_KEY = os.getenv("API_KEY", "abcdef12345")


def verify_api_key(x_api_key: str = Header(default=None, alias="X-API-Key")):
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Invalid API Key"
        )
