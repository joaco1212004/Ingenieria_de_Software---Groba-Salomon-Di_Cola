from fastapi import Header, HTTPException, status

API_KEY = "abcdef12345"


def verify_api_key(x_api_key: str = Header(default=None, alias="X-API-Key")):
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Invalid API Key"
        )
