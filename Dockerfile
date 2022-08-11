FROM python:3.9.13-alpine as base

RUN mkdir -p /vlrggapi

WORKDIR /vlrggapi

RUN apk add --update \
    gcc \
    curl \
    git \
    build-base

COPY requirements.txt .
RUN pip install --no-cache-dir  -r requirements.txt


FROM python:3.9.13-alpine as final

WORKDIR /vlrggapi
COPY --from=base /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY . .

CMD ["python", "main.py"]
HEALTHCHECK --interval=5s --timeout=3s CMD curl --fail http://127.0.0.1:3001/health || exit 1
