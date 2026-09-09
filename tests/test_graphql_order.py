from unittest.mock import MagicMock, patch

from bson import ObjectId

from app.constants import ROLES
from tests.conftest import graphql_request, make_token, make_user

PLACE_ORDER = """
mutation($cartId: ID!, $total: Float) {
  placeOrder(cartId: $cartId, total: $total) {
    success
    message
    order { _id }
  }
}
"""

ORDER_SEARCH = """
query($search: String) {
  orderSearch(search: $search) {
    orders { _id total }
  }
}
"""

ORDERS = """
query($page: Int, $limit: Int) {
  orders(page: $page, limit: $limit) {
    orders { _id }
    totalPages
    currentPage
    count
  }
}
"""

MY_ORDERS = """
query($page: Int, $limit: Int) {
  myOrders(page: $page, limit: $limit) {
    orders { _id }
    totalPages
    currentPage
    count
  }
}
"""

ORDER = """
query($id: ID!) {
  order(id: $id) {
    _id
    total
    totalTax
    totalWithTax
    cartId
    products
  }
}
"""

CANCEL_ORDER = """
mutation($orderId: ID!) {
  cancelOrder(orderId: $orderId) {
    success
  }
}
"""

UPDATE_ITEM_STATUS = """
mutation($itemId: ID!, $orderId: ID, $cartId: ID, $status: String) {
  updateOrderItemStatus(itemId: $itemId, orderId: $orderId, cartId: $cartId, status: $status) {
    success
    orderCancelled
    message
  }
}
"""


def _auth(mock_db, role="ROLE MEMBER"):
    user = make_user(role=role)
    mock_db.users.find_one.return_value = user
    return user, make_token(str(user["_id"]))


# ---------------------------------------------------------------- placeOrder


def test_place_order_requires_authentication(client):
    status, body = graphql_request(client, PLACE_ORDER, {"cartId": str(ObjectId())})
    assert status == 401


@patch("app.graphql.resolvers.order.requests.post")
def test_place_order_succeeds_and_sends_confirmation_email(mock_post, client, mock_db):
    user, token = _auth(mock_db)
    order_id = ObjectId()
    mock_db.orders.insert_one.return_value.inserted_id = order_id
    mock_db.orders.find_one.return_value = {"_id": order_id, "cart": ObjectId(), "total": 10}
    mock_db.carts.find_one.return_value = {"products": []}

    status, body = graphql_request(client, PLACE_ORDER, {"cartId": str(ObjectId()), "total": 10}, token)

    assert status == 200
    assert body["data"]["placeOrder"]["success"] is True
    assert body["data"]["placeOrder"]["order"]["_id"] == str(order_id)
    mock_post.assert_called_once()


@patch("app.graphql.resolvers.order.requests.post")
def test_place_order_skips_the_email_when_the_order_cannot_be_found(mock_post, client, mock_db):
    user, token = _auth(mock_db)
    mock_db.orders.insert_one.return_value.inserted_id = ObjectId()
    mock_db.orders.find_one.return_value = None

    status, body = graphql_request(client, PLACE_ORDER, {"cartId": str(ObjectId())}, token)

    assert status == 200
    assert body["data"]["placeOrder"]["success"] is True
    mock_post.assert_not_called()


@patch("app.graphql.resolvers.order.requests.post")
def test_place_order_skips_the_email_when_the_cart_cannot_be_found(mock_post, client, mock_db):
    user, token = _auth(mock_db)
    order_id = ObjectId()
    mock_db.orders.insert_one.return_value.inserted_id = order_id
    mock_db.orders.find_one.return_value = {"_id": order_id, "cart": ObjectId()}
    mock_db.carts.find_one.return_value = None

    status, body = graphql_request(client, PLACE_ORDER, {"cartId": str(ObjectId())}, token)

    assert status == 200
    assert body["data"]["placeOrder"]["success"] is True
    mock_post.assert_not_called()


@patch("app.graphql.resolvers.order.requests.post", side_effect=RuntimeError("network down"))
def test_place_order_still_succeeds_when_sending_the_email_fails(mock_post, client, mock_db):
    user, token = _auth(mock_db)
    order_id = ObjectId()
    mock_db.orders.insert_one.return_value.inserted_id = order_id
    mock_db.orders.find_one.return_value = {"_id": order_id, "cart": ObjectId(), "total": 5}
    mock_db.carts.find_one.return_value = {"products": []}

    status, body = graphql_request(client, PLACE_ORDER, {"cartId": str(ObjectId())}, token)

    assert status == 200
    assert body["data"]["placeOrder"]["success"] is True


def test_place_order_returns_400_on_an_unexpected_error(client, mock_db):
    user, token = _auth(mock_db)
    mock_db.orders.insert_one.side_effect = RuntimeError("boom")

    status, body = graphql_request(client, PLACE_ORDER, {"cartId": str(ObjectId())}, token)

    assert status == 400
    assert body["error"] == "Your request could not be processed. Please try again."


# --------------------------------------------------------------- orderSearch


def test_order_search_requires_authentication(client):
    status, body = graphql_request(client, ORDER_SEARCH, {"search": str(ObjectId())})
    assert status == 401


def test_order_search_with_no_search_value_returns_empty(client, mock_db):
    user, token = _auth(mock_db)

    status, body = graphql_request(client, ORDER_SEARCH, {}, token)

    assert status == 200
    assert body["data"]["orderSearch"]["orders"] == []


def test_order_search_with_an_invalid_id_returns_empty(client, mock_db):
    user, token = _auth(mock_db)

    status, body = graphql_request(client, ORDER_SEARCH, {"search": "not-an-id"}, token)

    assert status == 200
    assert body["data"]["orderSearch"]["orders"] == []


def test_order_search_finds_a_matching_order_for_a_member(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Member"])
    order_id = ObjectId()
    mock_db.orders.find.return_value = [
        {"_id": order_id, "cart": ObjectId(), "total": 12, "created": "2024-01-01"}
    ]
    mock_db.carts.find_one.return_value = {
        "_id": ObjectId(),
        "products": [{"quantity": 1, "purchasePrice": 12, "product": {"price": 12}}],
    }

    status, body = graphql_request(client, ORDER_SEARCH, {"search": str(order_id)}, token)

    assert status == 200
    assert len(body["data"]["orderSearch"]["orders"]) == 1


def test_order_search_as_admin_does_not_scope_to_the_caller(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Admin"])
    order_id = ObjectId()
    mock_db.orders.find.return_value = [{"_id": order_id, "cart": ObjectId(), "created": "x"}]
    mock_db.carts.find_one.return_value = {"_id": ObjectId(), "products": []}

    status, body = graphql_request(client, ORDER_SEARCH, {"search": str(order_id)}, token)

    assert status == 200
    called_query = mock_db.orders.find.call_args[0][0]
    assert "user" not in called_query


def test_order_search_filters_out_orders_with_no_cart(client, mock_db):
    user, token = _auth(mock_db)
    order_id = ObjectId()
    mock_db.orders.find.return_value = [{"_id": order_id, "cart": None}]
    mock_db.carts.find_one.return_value = None

    status, body = graphql_request(client, ORDER_SEARCH, {"search": str(order_id)}, token)

    assert status == 200
    assert body["data"]["orderSearch"]["orders"] == []


def test_order_search_returns_400_on_an_unexpected_error(client, mock_db):
    user, token = _auth(mock_db)
    mock_db.orders.find.side_effect = RuntimeError("boom")

    status, body = graphql_request(client, ORDER_SEARCH, {"search": str(ObjectId())}, token)

    assert status == 400


# ------------------------------------------------------------------- orders


def test_orders_requires_authentication(client):
    status, body = graphql_request(client, ORDERS, {})
    assert status == 401


def test_orders_lists_every_order_with_pagination(client, mock_db):
    user, token = _auth(mock_db)
    order_id = ObjectId()
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = [{"_id": order_id, "cart": ObjectId(), "total": 1, "created": "x"}]
    mock_db.orders.find.return_value = cursor
    mock_db.orders.count_documents.return_value = 1
    mock_db.carts.find_one.return_value = {"products": []}

    status, body = graphql_request(client, ORDERS, {"page": 1, "limit": 10}, token)

    assert status == 200
    assert body["data"]["orders"]["count"] == 1
    assert body["data"]["orders"]["currentPage"] == 1


def test_orders_returns_400_on_an_unexpected_error(client, mock_db):
    user, token = _auth(mock_db)
    mock_db.orders.find.side_effect = RuntimeError("boom")

    status, body = graphql_request(client, ORDERS, {}, token)

    assert status == 400


# ---------------------------------------------------------------- myOrders


def test_my_orders_requires_authentication(client):
    status, body = graphql_request(client, MY_ORDERS, {})
    assert status == 401


def test_my_orders_scopes_to_the_caller(client, mock_db):
    user, token = _auth(mock_db)
    order_id = ObjectId()
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = [{"_id": order_id, "cart": ObjectId(), "total": 1, "created": "x"}]
    mock_db.orders.find.return_value = cursor
    mock_db.orders.count_documents.return_value = 1
    mock_db.carts.find_one.return_value = {"products": []}

    status, body = graphql_request(client, MY_ORDERS, {}, token)

    assert status == 200
    called_query = mock_db.orders.find.call_args[0][0]
    assert called_query == {"user": user["_id"]}


def test_my_orders_returns_400_on_an_unexpected_error(client, mock_db):
    user, token = _auth(mock_db)
    mock_db.orders.find.side_effect = RuntimeError("boom")

    status, body = graphql_request(client, MY_ORDERS, {}, token)

    assert status == 400


# -------------------------------------------------------------------- order


def test_order_requires_authentication(client):
    status, body = graphql_request(client, ORDER, {"id": str(ObjectId())})
    assert status == 401


def test_order_returns_404_when_not_found(client, mock_db):
    user, token = _auth(mock_db)
    mock_db.orders.find_one.return_value = None

    status, body = graphql_request(client, ORDER, {"id": str(ObjectId())}, token)

    assert status == 404
    assert "message" in body


def test_order_returns_404_when_the_cart_is_missing(client, mock_db):
    user, token = _auth(mock_db)
    mock_db.orders.find_one.return_value = {"_id": ObjectId(), "cart": ObjectId()}
    mock_db.carts.find_one.return_value = None

    status, body = graphql_request(client, ORDER, {"id": str(ObjectId())}, token)

    assert status == 404


def test_order_returns_the_order_for_its_owner(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Member"])
    order_id = ObjectId()
    mock_db.orders.find_one.return_value = {"_id": order_id, "cart": ObjectId(), "total": 10}
    mock_db.carts.find_one.return_value = {
        "_id": ObjectId(),
        "products": [{"quantity": 1, "purchasePrice": 10, "product": {"price": 10}}],
    }

    status, body = graphql_request(client, ORDER, {"id": str(order_id)}, token)

    assert status == 200
    assert body["data"]["order"]["_id"] == str(order_id)
    called_query = mock_db.orders.find_one.call_args[0][0]
    assert called_query["user"] == user["_id"]


def test_order_populates_an_unpopulated_product_reference_and_its_brand(client, mock_db):
    # Exercises the full populate chain in _populate_cart_products/
    # _populate_cart_products_brand: one line item still holds a raw
    # ObjectId product reference (gets replaced by a real find_one lookup,
    # whose result then has its own `brand` ObjectId replaced the same
    # way), and a second line item whose `product` isn't a dict at all
    # (already missing/never resolved) to prove that one is just skipped
    # rather than raising.
    user, token = _auth(mock_db, role=ROLES["Member"])
    order_id = ObjectId()
    product_id = ObjectId()
    brand_id = ObjectId()
    mock_db.orders.find_one.return_value = {"_id": order_id, "cart": ObjectId(), "total": 10}
    mock_db.carts.find_one.return_value = {
        "_id": ObjectId(),
        "products": [
            {"quantity": 1, "purchasePrice": 10, "product": product_id},
            {"quantity": 1, "purchasePrice": 5, "product": None},
        ],
    }
    mock_db.products.find_one.return_value = {"_id": product_id, "price": 10, "brand": brand_id}
    mock_db.brands.find_one.return_value = {"_id": brand_id, "name": "Acme"}

    status, body = graphql_request(client, ORDER, {"id": str(order_id)}, token)

    assert status == 200
    assert body["data"]["order"]["_id"] == str(order_id)
    mock_db.products.find_one.assert_called_once_with({"_id": product_id})
    mock_db.brands.find_one.assert_called_once_with({"_id": brand_id})


def test_order_as_admin_does_not_scope_to_the_caller(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Admin"])
    order_id = ObjectId()
    mock_db.orders.find_one.return_value = {"_id": order_id, "cart": ObjectId()}
    mock_db.carts.find_one.return_value = {"_id": ObjectId(), "products": []}

    status, body = graphql_request(client, ORDER, {"id": str(order_id)}, token)

    assert status == 200
    called_query = mock_db.orders.find_one.call_args[0][0]
    assert "user" not in called_query


def test_order_returns_400_on_a_malformed_id(client, mock_db):
    user, token = _auth(mock_db)

    status, body = graphql_request(client, ORDER, {"id": "not-an-id"}, token)

    assert status == 400


# ------------------------------------------------------------------ cancelOrder


def test_cancel_order_requires_authentication(client):
    status, body = graphql_request(client, CANCEL_ORDER, {"orderId": str(ObjectId())})
    assert status == 401


def test_cancel_order_restocks_and_deletes(client, mock_db):
    user, token = _auth(mock_db)
    cart_id = ObjectId()
    mock_db.orders.find_one.return_value = {"_id": ObjectId(), "cart": cart_id}
    mock_db.carts.find_one.return_value = {
        "_id": cart_id,
        "products": [{"product": ObjectId(), "quantity": 2}],
    }

    status, body = graphql_request(client, CANCEL_ORDER, {"orderId": str(ObjectId())}, token)

    assert status == 200
    assert body["data"]["cancelOrder"]["success"] is True
    mock_db.products.bulk_write.assert_called_once()


def test_cancel_order_with_no_line_items_skips_the_restock_bulk_write(client, mock_db):
    user, token = _auth(mock_db)
    cart_id = ObjectId()
    mock_db.orders.find_one.return_value = {"_id": ObjectId(), "cart": cart_id}
    mock_db.carts.find_one.return_value = {"_id": cart_id, "products": []}

    status, body = graphql_request(client, CANCEL_ORDER, {"orderId": str(ObjectId())}, token)

    assert status == 200
    mock_db.products.bulk_write.assert_not_called()


def test_cancel_order_returns_400_when_the_order_does_not_exist(client, mock_db):
    user, token = _auth(mock_db)
    mock_db.orders.find_one.return_value = None

    status, body = graphql_request(client, CANCEL_ORDER, {"orderId": str(ObjectId())}, token)

    assert status == 400


# ------------------------------------------------------------ updateOrderItemStatus


def test_update_order_item_status_requires_authentication(client):
    status, body = graphql_request(client, UPDATE_ITEM_STATUS, {"itemId": str(ObjectId())})
    assert status == 401


def test_update_order_item_status_updates_without_cancelling(client, mock_db):
    user, token = _auth(mock_db)
    item_id = ObjectId()
    mock_db.carts.find_one.return_value = {"products": [{"_id": item_id, "product": ObjectId(), "quantity": 1}]}

    status, body = graphql_request(
        client, UPDATE_ITEM_STATUS, {"itemId": str(item_id), "status": "Shipped"}, token
    )

    assert status == 200
    assert body["data"]["updateOrderItemStatus"]["message"] == "Item status has been updated successfully!"
    assert body["data"]["updateOrderItemStatus"]["orderCancelled"] is None


def test_update_order_item_status_defaults_to_cancelled_when_status_is_omitted(client, mock_db):
    user, token = _auth(mock_db)
    item_id = ObjectId()
    cart_id = ObjectId()
    product_id = ObjectId()
    mock_db.carts.find_one.side_effect = [
        {"products": [{"_id": item_id, "product": product_id, "quantity": 3}]},
        {"products": [{"_id": item_id, "status": "Cancelled"}]},
    ]

    status, body = graphql_request(
        client,
        UPDATE_ITEM_STATUS,
        {"itemId": str(item_id), "orderId": str(ObjectId()), "cartId": str(cart_id)},
        token,
    )

    assert status == 200
    assert body["data"]["updateOrderItemStatus"]["orderCancelled"] is True


def test_update_order_item_status_cancels_a_single_item_without_cancelling_the_order(client, mock_db):
    user, token = _auth(mock_db)
    item_id = ObjectId()
    cart_id = ObjectId()
    mock_db.carts.find_one.side_effect = [
        {"products": [{"_id": item_id, "product": ObjectId(), "quantity": 1}]},
        {"products": [{"_id": item_id, "status": "Cancelled"}, {"_id": ObjectId(), "status": "Not processed"}]},
    ]

    status, body = graphql_request(
        client,
        UPDATE_ITEM_STATUS,
        {"itemId": str(item_id), "orderId": str(ObjectId()), "cartId": str(cart_id), "status": "Cancelled"},
        token,
    )

    assert status == 200
    body_data = body["data"]["updateOrderItemStatus"]
    assert body_data["message"] == "Item has been cancelled successfully!"
    assert body_data["orderCancelled"] is None


def test_update_order_item_status_admin_cancelling_the_whole_order_gets_a_different_message(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Admin"])
    item_id = ObjectId()
    cart_id = ObjectId()
    mock_db.carts.find_one.side_effect = [
        {"products": [{"_id": item_id, "product": ObjectId(), "quantity": 1}]},
        {"products": [{"_id": item_id, "status": "Cancelled"}]},
    ]

    status, body = graphql_request(
        client,
        UPDATE_ITEM_STATUS,
        {"itemId": str(item_id), "orderId": str(ObjectId()), "cartId": str(cart_id), "status": "Cancelled"},
        token,
    )

    assert status == 200
    assert body["data"]["updateOrderItemStatus"]["message"] == "Order has been cancelled successfully"


def test_update_order_item_status_returns_400_on_an_unexpected_error(client, mock_db):
    user, token = _auth(mock_db)
    mock_db.carts.find_one.return_value = None

    status, body = graphql_request(client, UPDATE_ITEM_STATUS, {"itemId": str(ObjectId())}, token)

    assert status == 400
