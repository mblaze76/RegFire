FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY deploy/requirements.txt /app/deploy/requirements.txt
RUN pip install --no-cache-dir -r deploy/requirements.txt && useradd --uid 10001 --create-home regfire
COPY . /app
RUN mkdir -p /app/.local /app/uploads && chown -R 10001:10001 /app/.local /app/uploads && chmod 700 /app/.local
EXPOSE 8080
CMD ["python","deploy/entrypoint.py"]
