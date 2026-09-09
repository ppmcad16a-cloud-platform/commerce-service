from flask import Blueprint, jsonify, request

from ..auth import load_current_user
from .context import GraphQLContext
from .errors import GENERIC_ERROR_MESSAGE, GraphQLHttpError
from .schema import schema

bp = Blueprint("graphql", __name__)


@bp.post("")
def graphql_view():
    payload = request.get_json(silent=True) or {}
    query = payload.get("query")

    if not query:
        return jsonify({"error": "Must provide a GraphQL query string."}), 400

    context = GraphQLContext(current_user=load_current_user())
    result = schema.execute(
        query,
        variable_values=payload.get("variables"),
        operation_name=payload.get("operationName"),
        context_value=context,
    )

    if result.errors:
        return _error_response(result.errors[0])

    return jsonify({"data": result.data}), 200


def _error_response(graphql_error):
    """Maps the first error back to the REST-shaped status/body every other
    service's `handleError` (client/app/utils/error.js) already knows how
    to read — see errors.py's module docstring for why. A malformed query
    (syntax/validation error) or a resolver bug neither of which raise one
    of our typed exceptions falls back to the same generic 400 every REST
    blueprint used for its own unexpected `except Exception`.
    """
    original = getattr(graphql_error, "original_error", None)
    if isinstance(original, GraphQLHttpError):
        return jsonify({original.body_key: original.message}), original.status_code

    return jsonify({"error": GENERIC_ERROR_MESSAGE}), 400
