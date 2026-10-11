# ============================================================
# Commerce Service - container image (Python / Flask / gunicorn)
#
# Multi-stage build:
#   1. "build"   installs the Python packages into a virtualenv
#   2. "runtime" copies only that virtualenv + the app code
#
# Security:
#   - runs as an unprivileged user (uid 10001), not root
#   - no compilers, tests, dev packages or .env files in the image
#   - served by gunicorn (production server), not Flask's dev server
# ============================================================

FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt


FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# A home directory is needed: gunicorn keeps its control socket there.
RUN useradd --uid 10001 --create-home --home-dir /home/app --shell /usr/sbin/nologin app

# pip/setuptools are not needed at runtime; removing them drops their CVEs.
RUN pip uninstall -y pip setuptools wheel 2>/dev/null || true

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY app ./app
COPY run.py gunicorn.conf.py ./

USER 10001
EXPOSE 3103

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3103/health', timeout=2)" || exit 1

# gunicorn reads gunicorn.conf.py from the working directory.
CMD ["gunicorn", "run:app"]
