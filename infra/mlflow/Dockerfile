FROM ghcr.io/mlflow/mlflow:v2.19.0

# La imagen oficial no trae driver de Postgres ni cliente S3.
RUN pip install --no-cache-dir psycopg2-binary==2.9.10 boto3==1.35.36
