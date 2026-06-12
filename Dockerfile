FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENV DATA_DIR=/data
VOLUME /data
EXPOSE 8080

CMD ["./entrypoint.sh"]
