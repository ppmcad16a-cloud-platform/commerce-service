from bson import ObjectId

from tests.conftest import graphql_request, make_token, make_user

ADD_CART = """
mutation($products: [CartItemInput]!) {
  addCart(products: $products) {
    success
    cartId
  }
}
"""

DELETE_CART = """
mutation($cartId: ID!) {
  deleteCart(cartId: $cartId) {
    success
  }
}
"""

ADD_CART_ITEM = """
mutation($cartId: ID!, $product: GenericScalar!) {
  addCartItem(cartId: $cartId, product: $product) {
    success
  }
}
"""

REMOVE_CART_ITEM = """
mutation($cartId: ID!, $productId: ID!) {
  removeCartItem(cartId: $cartId, productId: $productId) {
    success
  }
}
"""


def _one_item():
    return {"product": str(ObjectId()), "quantity": 2, "price": 10.5, "taxable": True}


def test_add_cart_requires_authentication(client):
    status, body = graphql_request(client, ADD_CART, {"products": [_one_item()]})
    assert status == 401
    assert body["error"] == "Unauthorized"


def test_add_cart_creates_a_cart_and_decrements_inventory(client, mock_db):
    user = make_user()
    token = make_token(str(user["_id"]))
    mock_db.users.find_one.return_value = user
    inserted_id = ObjectId()
    mock_db.carts.insert_one.return_value.inserted_id = inserted_id

    status, body = graphql_request(client, ADD_CART, {"products": [_one_item()]}, token)

    assert status == 200
    assert body["data"]["addCart"] == {"success": True, "cartId": str(inserted_id)}
    mock_db.products.bulk_write.assert_called_once()


def test_add_cart_with_no_items_skips_the_inventory_bulk_write(client, mock_db):
    user = make_user()
    token = make_token(str(user["_id"]))
    mock_db.users.find_one.return_value = user
    mock_db.carts.insert_one.return_value.inserted_id = ObjectId()

    status, body = graphql_request(client, ADD_CART, {"products": []}, token)

    assert status == 200
    assert body["data"]["addCart"]["success"] is True
    mock_db.products.bulk_write.assert_not_called()


def test_add_cart_returns_400_on_an_unexpected_error(client, mock_db):
    user = make_user()
    token = make_token(str(user["_id"]))
    mock_db.users.find_one.return_value = user
    mock_db.carts.insert_one.side_effect = RuntimeError("boom")

    status, body = graphql_request(client, ADD_CART, {"products": [_one_item()]}, token)

    assert status == 400
    assert body["error"] == "Your request could not be processed. Please try again."


def test_delete_cart_requires_authentication(client):
    status, body = graphql_request(client, DELETE_CART, {"cartId": str(ObjectId())})
    assert status == 401


def test_delete_cart_succeeds(client, mock_db):
    user = make_user()
    token = make_token(str(user["_id"]))
    mock_db.users.find_one.return_value = user

    status, body = graphql_request(client, DELETE_CART, {"cartId": str(ObjectId())}, token)

    assert status == 200
    assert body["data"]["deleteCart"]["success"] is True


def test_delete_cart_returns_400_on_a_malformed_id(client, mock_db):
    user = make_user()
    token = make_token(str(user["_id"]))
    mock_db.users.find_one.return_value = user

    status, body = graphql_request(client, DELETE_CART, {"cartId": "not-an-id"}, token)

    assert status == 400


def test_add_cart_item_requires_authentication(client):
    status, body = graphql_request(
        client, ADD_CART_ITEM, {"cartId": str(ObjectId()), "product": {"product": str(ObjectId())}}
    )
    assert status == 401


def test_add_cart_item_succeeds(client, mock_db):
    user = make_user()
    token = make_token(str(user["_id"]))
    mock_db.users.find_one.return_value = user

    status, body = graphql_request(
        client,
        ADD_CART_ITEM,
        {"cartId": str(ObjectId()), "product": {"product": str(ObjectId()), "quantity": 1}},
        token,
    )

    assert status == 200
    assert body["data"]["addCartItem"]["success"] is True


def test_add_cart_item_returns_400_on_a_malformed_id(client, mock_db):
    user = make_user()
    token = make_token(str(user["_id"]))
    mock_db.users.find_one.return_value = user

    status, body = graphql_request(
        client, ADD_CART_ITEM, {"cartId": "not-an-id", "product": {}}, token
    )

    assert status == 400


def test_remove_cart_item_requires_authentication(client):
    status, body = graphql_request(
        client, REMOVE_CART_ITEM, {"cartId": str(ObjectId()), "productId": str(ObjectId())}
    )
    assert status == 401


def test_remove_cart_item_succeeds(client, mock_db):
    user = make_user()
    token = make_token(str(user["_id"]))
    mock_db.users.find_one.return_value = user

    status, body = graphql_request(
        client,
        REMOVE_CART_ITEM,
        {"cartId": str(ObjectId()), "productId": str(ObjectId())},
        token,
    )

    assert status == 200
    assert body["data"]["removeCartItem"]["success"] is True


def test_remove_cart_item_returns_400_on_a_malformed_id(client, mock_db):
    user = make_user()
    token = make_token(str(user["_id"]))
    mock_db.users.find_one.return_value = user

    status, body = graphql_request(
        client, REMOVE_CART_ITEM, {"cartId": "not-an-id", "productId": str(ObjectId())}, token
    )

    assert status == 400
