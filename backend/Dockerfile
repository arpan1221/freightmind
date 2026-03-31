FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.3 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app/ ./app/
COPY data/ ./data/
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser
# Default 8000 for local Docker / Compose; Render injects PORT at runtime.
EXPOSE 8000
CMD ["sh", "-c", "exec uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
