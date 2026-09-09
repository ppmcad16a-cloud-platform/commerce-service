class GraphQLContext:
    """Passed as `context_value` to schema.execute() and read by resolvers
    as `info.context`. Built once per request in view.py — `current_user`
    is resolved eagerly (not lazily per-resolver) since almost every
    mutation/query needs it and a GraphQL request can select several
    top-level fields, which would otherwise mean re-verifying the same JWT
    once per field.
    """

    def __init__(self, current_user):
        self.current_user = current_user
