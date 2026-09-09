import jwt
from bson import ObjectId
from bson.errors import InvalidId
from flask import current_app, request

from .db import get_db
from .graphql.errors import ForbiddenError, UnauthorizedError


def load_current_user():
    """Reads `Authorization: Bearer <token>`, verifies it, and loads the
    User document — equivalent of config/passport.js's JwtStrategy callback.
    Returns None on any failure (missing header, bad prefix, invalid/
    expired signature, unknown user id). Called once per request (see
    app/graphql/view.py) to build the GraphQL execution context; resolvers
    read the result via `require_auth(info.context)` below rather than
    re-verifying the token themselves.
    """
    header = request.headers.get("Authorization")
    if not header or not header.startswith("Bearer "):
        return None

    token = header[7:].strip()
    try:
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except jwt.PyJWTError:
        return None

    user_id = payload.get("id")
    if not user_id:
        return None

    try:
        object_id = ObjectId(user_id)
    except (InvalidId, TypeError):
        return None

    return get_db().users.find_one({"_id": object_id})


def require_auth(context):
    """Equivalent of middleware/auth.js (`passport.authenticate('jwt', ...)`)
    for a resolver instead of an Express/Flask route: raises
    UnauthorizedError (mapped to a 401 by app/graphql/view.py) if the
    request's JWT didn't resolve to a real user, otherwise returns that
    user document. Resolvers that never call this never check auth at all,
    same as the original REST routes with no `auth` middleware applied.
    """
    if context.current_user is None:
        raise UnauthorizedError()
    return context.current_user


def require_role(context, *roles):
    """Equivalent of middleware/role.js's `role.check(...roles)`. Must be
    called after `require_auth(context)` in the same resolver — it assumes
    a user is already loaded and only defensively 401s if not, it doesn't
    authenticate on its own.
    """
    user = context.current_user
    if not user:
        raise UnauthorizedError()
    if user.get("role") not in roles:
        raise ForbiddenError()
