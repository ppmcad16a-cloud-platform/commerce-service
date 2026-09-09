from datetime import datetime, timezone

from bson import ObjectId


def to_jsonable(value):
    """Recursively converts a PyMongo document (or any nested structure
    containing one) into plain JSON-safe values: ObjectId -> hex string,
    datetime -> ISO-8601 string with a 'Z' suffix — matching Mongoose's own
    default `.toJSON()` shape (`_id` as a string, dates as ISO strings),
    which client/ already expects unchanged from the original Node service.
    PyMongo documents already use `_id` as the key natively, so — unlike
    the Java port — no field renaming is needed here, only type conversion.
    """
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    return value
