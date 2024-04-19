# Builder stage
FROM python:3.11 as builder
WORKDIR /vlrggapi
COPY ./requirements.txt /vlrggapi/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /vlrggapi/requirements.txt

# Final stage
FROM python:3.11-slim
WORKDIR /vlrggapi
COPY --from=builder /vlrggapi /vlrggapi
COPY . /vlrggapi
RUN pip install --no-cache-dir -r /vlrggapi/requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001"]