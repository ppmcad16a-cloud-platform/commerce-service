from unittest.mock import MagicMock

import jwt
import pytest
from bson import ObjectId

from app import create_app
from app import db as db_module

TEST_JWT_SECRET = "test-secret-must-be-at-least-32-bytes-long-1234567890"


class TestConfig:
    MONGO_URI = "mongodb://localhost:27017/test-db"
    JWT_SECRET = TEST_JWT_SECRET
    JWT_ALGORITHM = "HS256"
    BASE_API_URL = "api"
    NOTIFICATION_URL = "http://localhost:3104"


@pytest.fixture
def mock_db(monkeypatch):
    """Replaces app.db's module-global `_db` with a MagicMock, and makes
    init_db() a no-op so create_app() never opens a real MongoClient.
    Every blueprint's `get_db()` call reads `_db` fresh each time, so this
    single patch is picked up everywhere without needing to patch each
    blueprint module individually.
    """
    fake_db = MagicMock()
    monkeypatch.setattr(db_module, "init_db", lambda uri: fake_db)
    monkeypatch.setattr(db_module, "_db", fake_db)
    return fake_db


@pytest.fixture
def app(mock_db):
    application = create_app(TestConfig)
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def make_token(user_id="6a660443de971a14d415a3b7", secret=TEST_JWT_SECRET):
    return "Bearer " + jwt.encode({"id": user_id}, secret, algorithm="HS256")


def make_user(role="ROLE MEMBER", user_id=None, **overrides):
    user = {
        "_id": user_id or ObjectId(),
        "email": "user@example.com",
        "firstName": "First",
        "lastName": "Last",
        "role": role,
    }
    user.update(overrides)
    return user


def graphql_request(client, query, variables=None, token=None):
    """POSTs a GraphQL request the same way client/app/utils/graphql.js
    does, and returns (status_code, json_body) — every
    tests/test_graphql_*.py file drives the schema exclusively through this
    (real HTTP request -> view.py -> schema.execute -> resolver), never by
    calling a resolver function directly, so the HTTP status/body mapping
    in view.py stays covered too, not just the resolver logic underneath it.
    """
    headers = {"Authorization": token} if token else {}
    res = client.post(
        "/api/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )
    return res.status_code, res.get_json()
