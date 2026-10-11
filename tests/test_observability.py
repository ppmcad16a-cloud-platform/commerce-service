import io
import json
import logging

from app.observability import JsonFormatter, configure_logging


def test_health_is_ok_without_touching_the_db(client, mock_db):
    mock_db.command.side_effect = Exception("db down")

    res = client.get("/health")

    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_ready_is_200_when_mongo_answers(client):
    res = client.get("/ready")

    assert res.status_code == 200
    assert res.get_json() == {"status": "ready"}


def test_ready_is_503_when_mongo_is_down(client, mock_db):
    mock_db.command.side_effect = Exception("db down")

    res = client.get("/ready")

    assert res.status_code == 503
    assert res.get_json() == {"status": "not ready"}


def test_metrics_use_route_templates_not_raw_urls(client):
    client.post("/api/graphql", json={"query": "{ __typename }"})
    client.get("/api/does-not-exist/123")

    res = client.get("/metrics")
    text = res.get_data(as_text=True)

    assert res.status_code == 200
    assert res.mimetype == "text/plain"
    assert 'route="/api/graphql"' in text
    assert 'route="other"' in text
    assert 'service="commerce-service"' in text
    assert "process_cpu_seconds_total" in text or "python_info" in text


def test_requests_are_logged_as_json_with_level_by_status(client, caplog):
    with caplog.at_level(logging.INFO, logger="commerce-service"):
        client.post("/api/graphql", json={"query": "{ __typename }"})
        client.get("/api/missing")
        client.get("/health")  # probes are not logged

    records = [r for r in caplog.records if r.getMessage() == "request completed"]
    by_path = {r.path: r.levelname for r in records}
    assert by_path == {"/api/graphql": "INFO", "/api/missing": "WARNING"}


def test_server_errors_are_logged_at_error_level(app, caplog):
    @app.get("/boom")
    def boom():
        return "boom", 500

    with caplog.at_level(logging.INFO, logger="commerce-service"):
        app.test_client().get("/boom")

    record = next(r for r in caplog.records if r.getMessage() == "request completed")
    assert record.levelname == "ERROR"


def test_json_formatter_produces_one_json_object_per_line():
    record = logging.LogRecord("commerce-service", logging.WARNING, __file__, 1, "hi %s", ("there",), None)
    record.status = 404

    entry = json.loads(JsonFormatter().format(record))

    assert entry["level"] == "warning"
    assert entry["service"] == "commerce-service"
    assert entry["msg"] == "hi there"
    assert entry["status"] == 404
    assert "time" in entry


def test_json_formatter_includes_exceptions():
    try:
        raise ValueError("bad")
    except ValueError:
        import sys

        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())

    entry = json.loads(JsonFormatter().format(record))
    assert "ValueError: bad" in entry["err"]


def test_configure_logging_writes_json_to_the_given_stream():
    stream = io.StringIO()
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers, root.level
    try:
        logger = configure_logging("warning", stream=stream)
        logger.info("hidden")
        logger.warning("shown")
    finally:
        root.handlers, root.level = saved_handlers, saved_level

    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert [line["msg"] for line in lines] == ["shown"]


def test_configure_logging_defaults_to_stdout(capsys):
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers, root.level
    try:
        configure_logging().info("to stdout")
    finally:
        root.handlers, root.level = saved_handlers, saved_level

    assert json.loads(capsys.readouterr().out.strip())["msg"] == "to stdout"
