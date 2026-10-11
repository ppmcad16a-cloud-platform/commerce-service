import pytest

from app import create_app
from tests.conftest import TestConfig


def test_unmatched_route_returns_404(client):
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
    assert res.get_json() == "No API route found"


def test_graphql_endpoint_is_mounted_under_the_api_prefix(client):
    res = client.post("/api/graphql", json={"query": "query { orderSearch { orders { _id } } }"})
    # 401 (auth required for this particular field), not 404 — proves the
    # single GraphQL endpoint is mounted at the expected prefix and this
    # request actually reached it.
    assert res.status_code == 401


def test_graphql_endpoint_only_accepts_post(client):
    res = client.get("/api/graphql")
    assert res.status_code == 405


def test_refuses_to_start_when_mongo_is_unreachable(mock_db):
    mock_db.command.side_effect = Exception("no servers available")

    with pytest.raises(RuntimeError, match="MongoDB is not reachable"):
        create_app(TestConfig)


def test_startup_check_can_be_disabled(mock_db):
    mock_db.command.side_effect = Exception("no servers available")

    class NoCheckConfig(TestConfig):
        VERIFY_DB_ON_STARTUP = False

    assert create_app(NoCheckConfig) is not None
