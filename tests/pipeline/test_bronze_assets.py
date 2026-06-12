import boto3
import pytest
import responses
from dagster import materialize
from dagster_aws.s3 import S3Resource
from moto import mock_aws

from pipeline.assets.bronze import (
    LISTADO_POZOS_URL,
    PRODUCCION_NO_CONVENCIONAL_URL,
    bronze_key,
    listado_pozos_bronze,
    produccion_no_convencional_bronze,
)

BUCKET = 'datalake-bronze-test'
PARTITION = '2026-06-10'
FAKE_CSV = b'idpozo,empresa\n1,YPF\n2,PAE\n'

BRONZE_CASES = [
    (
        listado_pozos_bronze,
        LISTADO_POZOS_URL,
        'listado_pozos',
        'listado_pozos.csv',
    ),
    (
        produccion_no_convencional_bronze,
        PRODUCCION_NO_CONVENCIONAL_URL,
        'produccion_no_convencional',
        'produccion_no_convencional.csv',
    ),
]


@pytest.fixture
def entorno_s3(monkeypatch):
    monkeypatch.setenv('BRONZE_BUCKET', BUCKET)
    monkeypatch.delenv('S3_ENDPOINT_URL', raising=False)
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'testing')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'testing')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    with mock_aws():
        boto3.client('s3').create_bucket(Bucket=BUCKET)
        yield


def _materializar(asset_def, source_url):
    with responses.RequestsMock() as rsps:
        rsps.get(source_url, body=FAKE_CSV)
        return materialize(
            [asset_def],
            partition_key=PARTITION,
            resources={'s3': S3Resource()},
        )


@pytest.mark.parametrize(
    ('asset_def', 'source_url', 'dataset', 'filename'),
    BRONZE_CASES,
)
def test_sube_snapshot_crudo_a_la_particion(
    entorno_s3,
    asset_def,
    source_url,
    dataset,
    filename,
):
    resultado = _materializar(asset_def, source_url)

    assert resultado.success
    key = bronze_key(dataset, PARTITION, filename)
    objeto = boto3.client('s3').get_object(Bucket=BUCKET, Key=key)
    assert objeto['Body'].read() == FAKE_CSV


@pytest.mark.parametrize(
    ('asset_def', 'source_url', 'dataset', 'filename'),
    BRONZE_CASES,
)
def test_rematerializar_la_misma_particion_no_duplica(
    entorno_s3,
    asset_def,
    source_url,
    dataset,
    filename,
):
    _materializar(asset_def, source_url)
    _materializar(asset_def, source_url)

    prefijo = f'datalake/bronze/{dataset}/fecha_extraccion={PARTITION}/'
    listado = boto3.client('s3').list_objects_v2(Bucket=BUCKET, Prefix=prefijo)
    assert listado['KeyCount'] == 1
    assert listado['Contents'][0]['Key'] == bronze_key(dataset, PARTITION, filename)


@pytest.mark.parametrize(
    ('asset_def', 'source_url'),
    [case[:2] for case in BRONZE_CASES],
)
def test_falla_si_la_descarga_devuelve_error(entorno_s3, asset_def, source_url):
    with responses.RequestsMock() as rsps:
        for _ in range(4):
            rsps.get(source_url, status=503)
        resultado = materialize(
            [asset_def],
            partition_key=PARTITION,
            resources={'s3': S3Resource()},
            raise_on_error=False,
        )
    assert not resultado.success
