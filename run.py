"""Commerce microservice entry point: cart, order, merchant. Standalone —
shares the MongoDB database and JWT_SECRET with the other microservices,
and calls notification_server over HTTP for order-confirmation emails
(app/config.py's NOTIFICATION_URL, from the NOTIFICATION_URL env var).
This is the file `python run.py` / `flask --app run run` actually runs.
"""
import os

from dotenv import load_dotenv

# Must run before `from app import create_app` — app/config.py's Config
# class reads os.environ at import time, so .env has to be loaded first.
load_dotenv()

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3103))
    print(
        f"✓ commerce_server listening on port {port}. "
        f"Visit http://localhost:{port}/ in your browser."
    )
    app.run(host="0.0.0.0", port=port)
