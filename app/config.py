import os


class Config:
    """Central place that reads commerce_server/.env (via python-dotenv,
    loaded in run.py) and re-exports the values as typed attributes, so the
    rest of this service never touches os.environ directly. Mirrors
    config/keys.js from the Node microservices in this project.
    """

    PORT = int(os.environ.get("PORT", 3103))
    MONGO_URI = os.environ.get("MONGO_URI")

    # Must be identical across every microservice — each verifies the same
    # stateless JWT independently, with no central auth server.
    JWT_SECRET = os.environ.get("JWT_SECRET")
    JWT_ALGORITHM = "HS256"

    # Path prefix routes are mounted under, e.g. BASE_API_URL=api -> /api/...
    BASE_API_URL = os.environ.get("BASE_API_URL", "api")

    # Base URL of notification_server, used for the fire-and-forget order
    # confirmation email call in blueprints/order.py.
    NOTIFICATION_URL = os.environ.get("NOTIFICATION_URL")
