"""gunicorn settings - the production web server for this Flask app.

Run with:  gunicorn run:app      (this file is picked up automatically)

Why these values:
- ONE worker process with several threads: Prometheus metrics live in
  process memory, so with several worker processes each scrape would hit a
  random worker and see only its share. Scale out with more Kubernetes
  replicas instead of more workers.
- graceful_timeout: on SIGTERM (rolling update) finish in-flight requests
  for up to 20s before exiting - inside Kubernetes' 30s grace period.
- Logs: gunicorn's own messages use the same JSON formatter as the app.
  Access logs are off because the app already logs every request.
"""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '3103')}"
workers = 1
threads = int(os.environ.get("GUNICORN_THREADS", "8"))
worker_class = "gthread"
timeout = 30
graceful_timeout = 20
keepalive = 5
accesslog = None

logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "app.observability.JsonFormatter"}},
    "handlers": {
        "stdout": {"class": "logging.StreamHandler", "formatter": "json", "stream": "ext://sys.stdout"}
    },
    "root": {"level": os.environ.get("LOG_LEVEL", "INFO").upper(), "handlers": ["stdout"]},
    "loggers": {
        "gunicorn.error": {"level": "INFO", "handlers": ["stdout"], "propagate": False},
    },
}
