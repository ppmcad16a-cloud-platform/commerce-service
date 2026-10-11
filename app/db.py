from pymongo import MongoClient

# Equivalent of utils/db.js: a single Mongo client/database handle shared by
# the whole process. Unlike the Node services (which register Mongoose
# schemas up front), PyMongo is schema-less — there's nothing to "register",
# collections are just accessed by name directly wherever they're needed.
_client = None
_db = None

# How long a query waits to find a reachable MongoDB server before failing.
# PyMongo's default is 30s; a short value makes outages fail fast (and the
# /ready probe answer quickly) instead of hanging requests.
SERVER_SELECTION_TIMEOUT_MS = 5000


def init_db(mongo_uri):
    """Creates the shared MongoClient/Database for this process. Called
    once from the app factory. PyMongo connects lazily (on the first
    query); app/__init__.py calls ping() at startup to fail fast instead.
    """
    global _client, _db
    _client = MongoClient(mongo_uri, serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS)
    _db = _client.get_default_database()
    return _db


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized — call init_db() first.")
    return _db


def ping():
    """True when MongoDB answers a ping, False otherwise. Used by the
    /ready probe and the startup check."""
    try:
        get_db().command("ping")
        return True
    except Exception:  # noqa: BLE001 - any failure means "not ready"
        return False
