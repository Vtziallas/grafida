FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[test]" || true
COPY . .
RUN pip install --no-cache-dir -e ".[test]"
CMD ["sh", "-c", "python -m app.create_db && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
