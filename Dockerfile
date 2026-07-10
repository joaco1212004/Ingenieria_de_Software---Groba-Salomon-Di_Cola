FROM python:3.12-slim

WORKDIR /app

RUN pip install poetry==1.8.2

COPY pyproject.toml poetry.lock* ./

# Limpiar el cache de poetry/pip en la misma layer: con torch (~660MB de
# wheel cacheado) dejarlo inflaria la imagen en la EC2 chica.
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main \
    && rm -rf /root/.cache/pypoetry /root/.cache/pip

COPY . .

RUN poetry run dbt parse --project-dir dbt --profiles-dir dbt

CMD ["uvicorn", "api.main:api", "--host", "0.0.0.0", "--port", "8000"]
