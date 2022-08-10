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
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 CMD curl -f http://localhost:3001/health
