# syntax=docker/dockerfile:1
FROM python:3.12-slim@sha256:1148dbb014615300fa7e713b2f94f550c0d1c69780c0805f84f093ceee34dd0b
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api apps/api
COPY packages/sdk-python packages/sdk-python
COPY packages/contracts packages/contracts
COPY contracts contracts
COPY scripts scripts
COPY alembic.ini ./
RUN --mount=type=secret,id=system_ca \
    PIP_CERT=/run/secrets/system_ca pip install --no-cache-dir uv==0.13.4 && \
    SSL_CERT_FILE=/run/secrets/system_ca uv sync --frozen --no-dev --no-editable && \
    useradd --uid 10001 --create-home foundry
ENV PATH="/app/.venv/bin:$PATH"
USER foundry
