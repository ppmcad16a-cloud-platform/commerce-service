from datetime import datetime, timezone

from bson import ObjectId

from app.json_utils import to_jsonable


def test_object_id_becomes_hex_string():
    oid = ObjectId()
    assert to_jsonable(oid) == str(oid)


def test_naive_datetime_gets_utc_suffix():
    dt = datetime(2026, 1, 2, 3, 4, 5, 678000)
    assert to_jsonable(dt) == "2026-01-02T03:04:05.678Z"


def test_aware_datetime_converted_to_utc():
    dt = datetime(2026, 1, 2, 3, 4, 5, 678000, tzinfo=timezone.utc)
    assert to_jsonable(dt) == "2026-01-02T03:04:05.678Z"


def test_nested_dict_and_list():
    oid = ObjectId()
    value = {"a": [oid, {"b": oid}], "c": "plain", "d": 1}
    result = to_jsonable(value)
    assert result == {"a": [str(oid), {"b": str(oid)}], "c": "plain", "d": 1}


def test_plain_scalars_pass_through():
    assert to_jsonable(5) == 5
    assert to_jsonable("x") == "x"
    assert to_jsonable(None) is None
    assert to_jsonable(True) is True
