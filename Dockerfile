FROM docker.io/tiangolo/uvicorn-gunicorn:python3.11 as base

ENV POETRY_HOME=/opt/poetry
ENV POETRY_VENV=/opt/poetry-venv
ENV POETRY_CACHE_DIR=/app/venv

# Administrative tasks
RUN apt update -y && apt upgrade -y && apt install -y curl

RUN pip install --upgrade pip

# Creating a virtual environment just for poetry and install it with pip
RUN python3 -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install -U pip setuptools \
    && $POETRY_VENV/bin/pip install poetry

# Create a new stage from the base python image
FROM base as vlrggapi

RUN mkdir -p /vlrggapi

WORKDIR /vlrggapi

# Copy Poetry to app image
COPY --from=base ${POETRY_VENV} ${POETRY_VENV}

# Add Poetry to PATH
ENV PATH="${PATH}:${POETRY_VENV}/bin"

# Copy Application & dependencies
COPY poetry.lock pyproject.toml README.md main.py ./
COPY ./vlrggapi ./vlrggapi 

# Validate config && install dependencies
RUN poetry check && poetry install --only main --no-interaction --no-cache
ENV PYTHONUNBUFFERED=1

CMD [ "poetry", "run", "python", "main.py" ]
HEALTHCHECK --interval=5s --timeout=3s CMD curl --fail http://127.0.0.1:3001/health || exit 1