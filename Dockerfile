FROM python:3.7-alpine
LABEL maintainer="Andre Saddler <contact@rehkloos.com>"

LABEL build_date="2021-05-23"
RUN apk update && apk upgrade
RUN apk add --no-cache git make build-base linux-headers
WORKDIR /vlrggapi
COPY . .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
