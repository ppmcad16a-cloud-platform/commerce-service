from unittest.mock import MagicMock

import jwt
import pytest
from bson import ObjectId
from flask import Flask

from app import db as db_module
from app.auth import load_current_user, require_auth, require_role
from app.graphql.context import GraphQLContext
from app.graphql.errors import ForbiddenError, UnauthorizedError

SECRET = "test-secret-must-be-at-least-32-bytes-long-1234567890"


def build_app():
    app = Flask(__name__)
    app.config["JWT_SECRET"] = SECRET
    app.config["JWT_ALGORITHM"] = "HS256"
    return app


@pytest.fixture
def mock_db(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(db_module, "_db", fake)
    return fake


@pytest.fixture
def app():
    return build_app()


def _get_with_auth_header(app, header=None):
    """load_current_user() reads flask.request, so it must run inside a
    real request context — a plain test_request_context is enough, no
    routing/view function needed."""
    headers = {"Authorization": header} if header else {}
    with app.test_request_context("/", headers=headers):
        return load_current_user()


def test_no_authorization_header_returns_none(app):
    assert _get_with_auth_header(app) is None


def test_header_without_bearer_prefix_returns_none(app):
    assert _get_with_auth_header(app, "Basic abc") is None


def test_malformed_token_returns_none(app):
    assert _get_with_auth_header(app, "Bearer not-a-jwt") is None


def test_token_wrong_secret_returns_none(app):
    token = jwt.encode(
        {"id": str(ObjectId())}, "a-totally-different-secret-32-bytes-long", algorithm="HS256"
    )
    assert _get_with_auth_header(app, f"Bearer {token}") is None


def test_token_without_id_claim_returns_none(app):
    token = jwt.encode({"foo": "bar"}, SECRET, algorithm="HS256")
    assert _get_with_auth_header(app, f"Bearer {token}") is None


def test_token_with_malformed_id_returns_none(app):
    token = jwt.encode({"id": "not-an-object-id"}, SECRET, algorithm="HS256")
    assert _get_with_auth_header(app, f"Bearer {token}") is None


def test_token_for_unknown_user_returns_none(app, mock_db):
    mock_db.users.find_one.return_value = None
    token = jwt.encode({"id": str(ObjectId())}, SECRET, algorithm="HS256")
    assert _get_with_auth_header(app, f"Bearer {token}") is None


def test_valid_token_loads_the_user_document(app, mock_db):
    user_id = ObjectId()
    mock_db.users.find_one.return_value = {"_id": user_id, "role": "ROLE MEMBER"}
    token = jwt.encode({"id": str(user_id)}, SECRET, algorithm="HS256")

    user = _get_with_auth_header(app, f"Bearer {token}")

    assert user["_id"] == user_id


def test_require_auth_raises_unauthorized_when_no_user():
    with pytest.raises(UnauthorizedError):
        require_auth(GraphQLContext(current_user=None))


def test_require_auth_returns_the_user_when_present():
    user = {"_id": ObjectId(), "role": "ROLE MEMBER"}
    assert require_auth(GraphQLContext(current_user=user)) is user


def test_require_role_raises_forbidden_for_wrong_role():
    context = GraphQLContext(current_user={"role": "ROLE MEMBER"})
    with pytest.raises(ForbiddenError):
        require_role(context, "ROLE ADMIN")


def test_require_role_allows_matching_role():
    context = GraphQLContext(current_user={"role": "ROLE ADMIN"})
    require_role(context, "ROLE ADMIN")  # does not raise


def test_require_role_raises_unauthorized_without_a_user():
    # Defensive branch: require_role is always called after require_auth in
    # every real resolver (which already raises first if there's no user),
    # so this only exercises require_role's own standalone guard.
    with pytest.raises(UnauthorizedError):
        require_role(GraphQLContext(current_user=None), "ROLE ADMIN")
