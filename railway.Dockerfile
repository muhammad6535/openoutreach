FROM ghcr.io/eracle/openoutreach:latest AS base

USER root

RUN apt-get update && apt-get install -y --no-install-recommends supervisor && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir gunicorn psycopg2-binary whitenoise

COPY linkedin/llm.py /app/linkedin/llm.py
COPY linkedin/browser/launch.py /app/linkedin/browser/launch.py
COPY linkedin/django_settings.py /app/linkedin/django_settings.py
COPY linkedin/admin.py /app/linkedin/admin.py
COPY linkedin/urls.py /app/linkedin/urls.py
COPY linkedin/templates/ /app/linkedin/templates/
COPY wsgi.py /app/wsgi.py
COPY railway/start.sh /start
COPY railway/run_daemon.py /app/railway/run_daemon.py
COPY railway/supervisord.conf /etc/supervisor/conf.d/openoutreach.conf

RUN chmod +x /start && mkdir -p /app/staticfiles /app/data /app/logs && chown ubuntu:ubuntu /app/staticfiles /app/data /app/logs

ENTRYPOINT []
CMD ["/start"]
