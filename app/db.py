from pymongo import MongoClient

# Equivalent of utils/db.js: a single Mongo client/database handle shared by
# the whole process. Unlike the Node services (which register Mongoose
# schemas up front), PyMongo is schema-less — there's nothing to "register",
# collections are just accessed by name directly wherever they're needed.
_client = None
_db = None


def init_db(mongo_uri):
    """Creates the shared MongoClient/Database for this process. Called
    once from the app factory. Connection failures surface lazily on first
    actual query (PyMongo, like the Node driver, doesn't eagerly connect),
    same non-fail-fast behavior as the Node services' setupDB().
    """
    global _client, _db
    _client = MongoClient(mongo_uri)
    _db = _client.get_default_database()
    return _db


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized — call init_db() first.")
    return _db
