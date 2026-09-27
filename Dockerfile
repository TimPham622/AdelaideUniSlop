FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /uvx /bin/
WORKDIR /app
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 PATH="/app/.venv/bin:$PATH" EMBEDDING_CACHE=/models
COPY pyproject.toml uv.lock ./
COPY backend ./backend
RUN uv sync --frozen --no-dev
COPY data ./data
COPY alembic.ini ./
RUN python -c "from slop.search import encoder; encoder()"
RUN useradd --create-home app && chown -R app:app /app /models
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && slop load-fixtures && slop embed && uvicorn slop.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
