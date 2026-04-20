FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY server/pyproject.toml server/uv.lock ./
RUN uv sync --frozen --no-dev

COPY server/ .

ENV FLASK_SECRET=dev-secret-change-in-prod

EXPOSE 5000

CMD ["uv", "run", "python", "main.py", "-c", "config.yaml"]
