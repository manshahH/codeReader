FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY app /app/app
RUN pip install --no-cache-dir -e /app

CMD uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
