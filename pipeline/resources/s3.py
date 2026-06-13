"""Recurso S3 compartido por los assets del pipeline (ADR-0010).

El mismo código sirve para los tres entornos:
- Local / integration test del CI: S3_ENDPOINT_URL apunta al MinIO del
  docker-compose (doble de S3, sin credenciales AWS).
- Unit tests: moto mockea boto3 en memoria, sin endpoint.
- Producción (EC2): S3_ENDPOINT_URL vacío => boto3 va al S3 real de AWS
  con las credenciales inyectadas por el deploy (ADR-0005).
"""

import os

from dagster_aws.s3 import S3Resource


def s3_resource_from_env() -> S3Resource:
    """Construye el S3Resource según las variables de entorno."""
    return S3Resource(endpoint_url=os.getenv("S3_ENDPOINT_URL") or None)
