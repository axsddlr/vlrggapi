FROM tiangolo/uvicorn-gunicorn:python3.9-alpine3.14 as base

RUN mkdir -p /vlrggapi

WORKDIR /vlrggapi

COPY requirements.txt .
RUN pip install --no-cache-dir  -r requirements.txt


FROM tiangolo/uvicorn-gunicorn:python3.9-alpine3.14 as final

WORKDIR /vlrggapi
COPY --from=base /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY . .

RUN apk add curl

CMD ["python", "main.py"]
HEALTHCHECK --interval=5s --timeout=3s CMD curl --fail http://127.0.0.1:3001/health || exit 1
