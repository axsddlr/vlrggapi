FROM python:3.13-alpine AS builder

WORKDIR /vlrggapi

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

FROM python:3.13-alpine

WORKDIR /vlrggapi

RUN addgroup -S vlrggapi && adduser -S -G vlrggapi -h /vlrggapi -s /sbin/nologin vlrggapi

COPY --from=builder --chown=vlrggapi:vlrggapi /usr/local /usr/local
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
