"""HTTP-status-carrying exceptions raised from resolvers.

Standard GraphQL-over-HTTP always responds 200 and reports failures in a
top-level `errors` array — but this project's `client/app/utils/error.js`
(shared by every service, unchanged here) branches on the HTTP *status*
(400/401/403) and reads `err.response.data.error`/`.message` the REST way.
Rather than rewrite that shared client utility, `app/graphql/view.py`
inspects the *original* Python exception graphql-core wraps around a
resolver's raise (`GraphQLError.original_error`) and, for these specific
types, replies with the old REST-shaped status + body instead of the
standard `{"errors": [...]}` envelope. A resolver exception that ISN'T one
of these still gets treated as a bug and falls back to the generic 400,
same as every REST blueprint's own bare `except Exception`.
"""

GENERIC_ERROR_MESSAGE = "Your request could not be processed. Please try again."


class GraphQLHttpError(Exception):
    """Base class every typed resolver error inherits from. `body_key` is
    the JSON key the message is nested under in the HTTP response — "error"
    for every case except NotFoundError, which mirrors the original REST
    order-lookup 404's `{"message": ...}` shape.
    """

    status_code = 400
    body_key = "error"

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class UnauthorizedError(GraphQLHttpError):
    status_code = 401

    def __init__(self, message="Unauthorized"):
        super().__init__(message)


class ForbiddenError(GraphQLHttpError):
    status_code = 403

    def __init__(self, message="You are not allowed to make this request."):
        super().__init__(message)


class NotFoundError(GraphQLHttpError):
    status_code = 404
    body_key = "message"


class BadRequestError(GraphQLHttpError):
    status_code = 400
