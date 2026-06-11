"""Unit tests del asset de extracción bronze.

S3 se mockea en memoria con moto y la descarga HTTP con responses,
así el test corre en el job `test` del CI sin servicios externos.
"""

import boto3
import pytest
import responses
from dagster import materialize
from dagster_aws.s3 import S3Resource
from moto import mock_aws

from pipeline.assets.bronze import (
    LISTADO_POZOS_URL,
    bronze_key,
    listado_pozos_bronze,
)

BUCKET = "datalake-bronze-test"
PARTITION = "2026-06-10"
FAKE_CSV = b"idpozo,empresa\n1,YPF\n2,PAE\n"


@pytest.fixture
def entorno_s3(monkeypatch):
    """Bucket moto + env vars que espera el asset."""
    monkeypatch.setenv("BRONZE_BUCKET", BUCKET)
    monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        boto3.client("s3").create_bucket(Bucket=BUCKET)
        yield


def _materializar():
    with responses.RequestsMock() as rsps:
        rsps.get(LISTADO_POZOS_URL, body=FAKE_CSV)
        return materialize(
            [listado_pozos_bronze],
            partition_key=PARTITION,
            resources={"s3": S3Resource()},
        )


def test_sube_snapshot_crudo_a_la_particion(entorno_s3):
    resultado = _materializar()

    assert resultado.success
    key = bronze_key("listado_pozos", PARTITION, "listado_pozos.csv")
    objeto = boto3.client("s3").get_object(Bucket=BUCKET, Key=key)
    assert objeto["Body"].read() == FAKE_CSV


def test_rematerializar_la_misma_particion_no_duplica(entorno_s3):
    _materializar()
    _materializar()

    prefijo = f"datalake/bronze/listado_pozos/fecha_extraccion={PARTITION}/"
    listado = boto3.client("s3").list_objects_v2(Bucket=BUCKET, Prefix=prefijo)
    assert listado["KeyCount"] == 1


def test_falla_si_la_descarga_devuelve_error(entorno_s3):
    with responses.RequestsMock() as rsps:
        rsps.get(LISTADO_POZOS_URL, status=503)
        resultado = materialize(
            [listado_pozos_bronze],
            partition_key=PARTITION,
            resources={"s3": S3Resource()},
            raise_on_error=False,
        )
    assert not resultado.success
