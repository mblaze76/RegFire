FROM python:3.13-alpine3.24@sha256:2d9aefe2fef018a7eb2c13064c89c71929800fd2e5dccdbf52ea5da5bb8d929a
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apk upgrade --no-cache
WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY deploy/requirements.txt /app/deploy/requirements.txt
RUN pip install --no-cache-dir -r deploy/requirements.txt && addgroup -g 10001 regfire && adduser -D -u 10001 -G regfire regfire
COPY . /app
RUN mkdir -p /app/.local /app/uploads && chown -R 10001:10001 /app/.local /app/uploads && chmod 700 /app/.local
EXPOSE 8080
CMD ["python","deploy/entrypoint.py"]
