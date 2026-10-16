# The api image also runs the load. The supplied data/ is mounted at run time,
# never copied in, and .env is never in the build context (.dockerignore).
FROM python:3.12.8-slim-bookworm

WORKDIR /app
COPY pyproject.toml ./
COPY pipeline ./pipeline
COPY api ./api
COPY evals ./evals
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
