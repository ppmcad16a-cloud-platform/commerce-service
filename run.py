"""Commerce microservice entry point: cart, order, merchant. Standalone —
shares the MongoDB database and JWT_SECRET with the other microservices,
and calls notification-service over HTTP for order-confirmation emails
(app/config.py's NOTIFICATION_URL, from the NOTIFICATION_URL env var).

Production (container):  gunicorn run:app   (settings in gunicorn.conf.py)
Local development:       python run.py      (Flask's built-in dev server)
"""
import os

from dotenv import load_dotenv

# Must run before `from app import create_app` — app/config.py's Config
# class reads os.environ at import time, so .env has to be loaded first.
load_dotenv()

from app import create_app  # noqa: E402
from app.observability import configure_logging  # noqa: E402

logger = configure_logging(os.environ.get("LOG_LEVEL", "INFO"))

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3103))
    logger.info("commerce-service listening (dev server)", extra={"port": port})
    app.run(host="0.0.0.0", port=port)
