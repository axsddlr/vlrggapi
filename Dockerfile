FROM python:3.14.7-alpine AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

WORKDIR /vlrggapi

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

FROM python:3.14.7-alpine

WORKDIR /vlrggapi

ENV PATH="/vlrggapi/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup -S vlrggapi && adduser -S -G vlrggapi -h /vlrggapi -s /sbin/nologin vlrggapi

COPY --from=builder --chown=vlrggapi:vlrggapi /vlrggapi/.venv /vlrggapi/.venv
COPY --chown=vlrggapi:vlrggapi api ./api
COPY --chown=vlrggapi:vlrggapi models ./models
COPY --chown=vlrggapi:vlrggapi routers ./routers
COPY --chown=vlrggapi:vlrggapi utils ./utils
COPY --chown=vlrggapi:vlrggapi main.py .

USER vlrggapi

EXPOSE 3001

CMD ["python", "main.py"]
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request, json; r = urllib.request.urlopen('http://127.0.0.1:3001/v2/health', timeout=3); assert json.loads(r.read())['status'] == 'success'"
