import pytest

from app import db as db_module


def test_init_db_sets_client_and_returns_database(monkeypatch):
    monkeypatch.setattr(db_module, "_client", None)
    monkeypatch.setattr(db_module, "_db", None)

    result = db_module.init_db("mongodb://localhost:27017/test-db")

    assert db_module._client is not None
    assert db_module._db is result
    assert result.name == "test-db"


def test_get_db_raises_when_not_initialized(monkeypatch):
    monkeypatch.setattr(db_module, "_db", None)

    with pytest.raises(RuntimeError):
        db_module.get_db()


def test_get_db_returns_initialized_database(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(db_module, "_db", sentinel)

    assert db_module.get_db() is sentinel
