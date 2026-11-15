# Stage 1: Build web frontend with Node + pnpm
FROM node:22-slim AS web-builder
WORKDIR /workspace/web

COPY web/package.json web/pnpm-lock.yaml ./
RUN npm install -g "$(node -p 'require("./package.json").packageManager')" \
    && pnpm install --frozen-lockfile

COPY web/ ./
RUN pnpm build

# Stage 2: Python 3.11 runtime with uv-locked dependencies + built web dist
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /workspace/api

COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --frozen --no-dev

COPY api/ /workspace/api/
COPY --from=web-builder /workspace/web/dist /workspace/web/dist

ENV PATH="/workspace/api/.venv/bin:${PATH}"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
