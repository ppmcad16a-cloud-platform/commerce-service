from flask import Flask, jsonify
from flask_cors import CORS

from . import db as db_module
from .config import Config
from .graphql import bp as graphql_bp


def create_app(config_object=Config):
    """Application factory — equivalent of index.js: builds the Flask app,
    applies open CORS (client and services are different origins by
    design, same as the Node services' bare `cors()`), connects to Mongo,
    and mounts the single GraphQL endpoint under BASE_API_URL. Kept as a
    factory (rather than a module-level app instance) so tests can build
    an app without a real MongoDB connection — see tests/conftest.py.

    Cart/order/merchant used to each be their own REST blueprint (still in
    git history); this service is now a single GraphQL schema
    (app/graphql/schema.py) behind one POST endpoint instead — see
    CLAUDE.md's commerce_server section for the full rationale, and
    api_gateway/index.js + client/'s Cart/Order/Merchant actions.js for the
    other two places that changed to match.
    """
    app = Flask(__name__)
    app.config.from_object(config_object)

    CORS(app)

    # Qualified module access (not `from .db import init_db`) so tests can
    # monkeypatch `app.db.init_db`/`app.db._db` directly and have it take
    # effect here regardless of import order — see tests/conftest.py.
    db_module.init_db(app.config["MONGO_URI"])

    api_prefix = f"/{app.config['BASE_API_URL']}"
    app.register_blueprint(graphql_bp, url_prefix=f"{api_prefix}/graphql")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify("No API route found"), 404

    return app
