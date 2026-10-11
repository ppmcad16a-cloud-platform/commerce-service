"""Logging, metrics and health probes for the commerce service.

Same conventions as the Node services (see their lib/observability.js):

- Logs: one JSON object per line on stdout. In Kubernetes, Grafana Alloy
  ships stdout to Loki where the fields (service, level, method, status ...)
  are searchable. Request headers are never logged, so tokens can't leak.
- Metrics: Prometheus format on GET /metrics, including the
  ``http_request_duration_seconds`` histogram (Rate / Errors / Duration)
  labelled with the Flask *route template*, never the raw URL.
- Probes: GET /health (liveness, no DB) and GET /ready (readiness, pings
  MongoDB).
"""
import json
import logging
import sys
import time
from datetime import datetime, timezone

from flask import Response, g, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    GCCollector,
    Histogram,
    PlatformCollector,
    ProcessCollector,
    generate_latest,
)

SERVICE_NAME = "commerce-service"

# Probe and scrape endpoints are hit every few seconds by Kubernetes and
# Prometheus - logging them would drown out real traffic.
QUIET_PATHS = {"/health", "/ready", "/metrics"}

# Attributes every LogRecord has; anything else was passed via `extra=`.
_STANDARD_ATTRS = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Formats a log record as a single JSON line."""

    def format(self, record):
        entry = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "service": SERVICE_NAME,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        entry.update(
            {key: value for key, value in vars(record).items() if key not in _STANDARD_ATTRS}
        )
        if record.exc_info:
            entry["err"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level="INFO", stream=None):
    """Sends every log record (ours, Flask's, gunicorn's) to stdout as JSON."""
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    return logging.getLogger(SERVICE_NAME)


def _route_label():
    # url_rule is the matched route template (e.g. "/api/graphql"); None
    # for 404s, which all share one label.
    return request.url_rule.rule if request.url_rule else "other"


def _log_level_for(status):
    if status >= 500:
        return logging.ERROR
    if status >= 400:
        return logging.WARNING
    return logging.INFO


def init_observability(app, is_ready):
    """Registers /health, /ready, /metrics and per-request logging+metrics.

    ``is_ready`` is a zero-argument callable returning True when the
    service can serve traffic (i.e. MongoDB answers a ping).
    """
    logger = logging.getLogger(SERVICE_NAME)

    # A private registry per app (instead of prometheus_client's global
    # one) so tests can build many apps without "duplicated timeseries".
    registry = CollectorRegistry()
    ProcessCollector(registry=registry)
    PlatformCollector(registry=registry)
    GCCollector(registry=registry)
    http_duration = Histogram(
        "http_request_duration_seconds",
        "Duration of HTTP requests in seconds",
        ["method", "route", "status_code", "service"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        registry=registry,
    )

    @app.before_request
    def _start_timer():
        g.request_start = time.perf_counter()

    @app.after_request
    def _record(response):
        duration = time.perf_counter() - g.request_start
        http_duration.labels(
            request.method, _route_label(), str(response.status_code), SERVICE_NAME
        ).observe(duration)
        if request.path not in QUIET_PATHS:
            logger.log(
                _log_level_for(response.status_code),
                "request completed",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": round(duration * 1000, 1),
                },
            )
        return response

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/ready")
    def ready():
        if is_ready():
            return jsonify(status="ready")
        return jsonify(status="not ready"), 503

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), mimetype=CONTENT_TYPE_LATEST)

    return registry
