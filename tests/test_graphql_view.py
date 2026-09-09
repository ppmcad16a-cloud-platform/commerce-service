def test_missing_query_string_returns_400(client):
    res = client.post("/api/graphql", json={})
    assert res.status_code == 400
    assert res.get_json() == {"error": "Must provide a GraphQL query string."}


def test_request_with_no_json_body_returns_400(client):
    res = client.post("/api/graphql", data="not json", content_type="text/plain")
    assert res.status_code == 400


def test_malformed_query_syntax_falls_back_to_the_generic_400(client):
    res = client.post("/api/graphql", json={"query": "{ this is not valid graphql"})
    assert res.status_code == 400
    assert res.get_json() == {"error": "Your request could not be processed. Please try again."}


def test_unknown_field_falls_back_to_the_generic_400(client):
    # Valid GraphQL syntax, but `doesNotExist` isn't a field on Query —
    # graphql-core's own validation phase rejects this before any resolver
    # runs, so `original_error` is None (not one of our typed exceptions).
    res = client.post("/api/graphql", json={"query": "{ doesNotExist }"})
    assert res.status_code == 400
    assert res.get_json() == {"error": "Your request could not be processed. Please try again."}


def test_successful_query_is_wrapped_in_a_data_envelope(client, mock_db):
    mock_db.merchants.find_one.return_value = None
    mock_db.merchants.insert_one.return_value.inserted_id = None

    res = client.post(
        "/api/graphql",
        json={
            "query": "mutation($n:String,$e:String,$p:String,$b:String){ addMerchant(name:$n,email:$e,phoneNumber:$p,business:$b) { success } }",
            "variables": {"n": "A", "e": "a@test.com", "p": "1234567890", "b": "a business description"},
        },
    )

    assert res.status_code == 200
    body = res.get_json()
    assert "data" in body
    assert "error" not in body
