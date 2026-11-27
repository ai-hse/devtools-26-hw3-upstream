FROM python:3.12-slim

ENV HOST=0.0.0.0 \
    PORT=8080 \
    DATA_DIR=/data

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN groupadd --gid 10001 app \
 && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
 && mkdir -p /data \
 && chown 10001:10001 /data

USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["python3", "app/server.py"]