FROM python:3.12-slim

WORKDIR /app

RUN pip install poetry==1.8.2

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --without dev

COPY . .

CMD ["uvicorn", "api.main:api", "--host", "0.0.0.0", "--port", "8000"]
