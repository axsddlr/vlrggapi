FROM python:3.10-alpine as base

RUN apk update && apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    curl \
    && pip install --upgrade pip

WORKDIR /vlrggapi

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001"]
HEALTHCHECK --interval=5s --timeout=3s CMD curl --fail http://127.0.0.1:3001/health || exit 1
