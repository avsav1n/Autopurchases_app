FROM python:3.12-slim AS builder
RUN apt-get update &&\
    apt-get install -y --no-install-recommends gettext 
WORKDIR /app
COPY . .
RUN python3 -m venv /app/venv &&\
    /app/venv/bin/pip install --no-cache-dir -r requirements.txt &&\
    /app/venv/bin/django-admin compilemessages

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/venv/bin:$PATH \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8
EXPOSE 8000
ENTRYPOINT [ "/app/docker-entrypoint.sh" ]