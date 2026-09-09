from unittest.mock import MagicMock

from bson import ObjectId

from app.constants import ROLES
from tests.conftest import graphql_request, make_token, make_user

ADD_MERCHANT = """
mutation($name: String, $email: String, $phoneNumber: String, $brandName: String, $business: String) {
  addMerchant(name: $name, email: $email, phoneNumber: $phoneNumber, brandName: $brandName, business: $business) {
    success
    message
    merchant { _id name }
  }
}
"""

MERCHANT_SEARCH = """
query($search: String) {
  merchantSearch(search: $search) {
    merchants { _id name brand }
  }
}
"""

MERCHANTS = """
query($page: Int, $limit: Int) {
  merchants(page: $page, limit: $limit) {
    merchants { _id name }
    totalPages
    currentPage
    count
  }
}
"""

SET_MERCHANT_ACTIVE = """
mutation($merchantId: ID!, $isActive: Boolean!) {
  setMerchantActive(merchantId: $merchantId, isActive: $isActive) {
    success
  }
}
"""

APPROVE_MERCHANT = """
mutation($merchantId: ID!) {
  approveMerchant(merchantId: $merchantId) {
    success
  }
}
"""

REJECT_MERCHANT = """
mutation($merchantId: ID!) {
  rejectMerchant(merchantId: $merchantId) {
    success
  }
}
"""

MERCHANT_SIGNUP = """
mutation($token: String!, $email: String, $firstName: String, $lastName: String, $password: String) {
  merchantSignup(token: $token, email: $email, firstName: $firstName, lastName: $lastName, password: $password) {
    success
  }
}
"""

DELETE_MERCHANT = """
mutation($merchantId: ID!) {
  deleteMerchant(merchantId: $merchantId) {
    success
    message
    deletedCount
  }
}
"""


def _auth(mock_db, role="ROLE MEMBER"):
    user = make_user(role=role)
    mock_db.users.find_one.return_value = user
    return user, make_token(str(user["_id"]))


def _valid_merchant_vars(**overrides):
    body = {
        "name": "Bob",
        "email": "bob@test.com",
        "phoneNumber": "1234567890",
        "brandName": "Bob's Brand",
        "business": "A fine business selling things",
    }
    body.update(overrides)
    return body


# ------------------------------------------------------------------ addMerchant


def test_add_merchant_does_not_require_authentication(client, mock_db):
    mock_db.merchants.find_one.return_value = None
    mock_db.merchants.insert_one.return_value.inserted_id = ObjectId()

    status, body = graphql_request(client, ADD_MERCHANT, _valid_merchant_vars())

    assert status == 200
    assert body["data"]["addMerchant"]["success"] is True


def test_add_merchant_rejects_a_missing_name_or_email(client, mock_db):
    status, body = graphql_request(client, ADD_MERCHANT, _valid_merchant_vars(name=None))
    assert status == 400
    assert "name and email" in body["error"]


def test_add_merchant_rejects_a_missing_business(client, mock_db):
    status, body = graphql_request(client, ADD_MERCHANT, _valid_merchant_vars(business=None))
    assert status == 400
    assert "business description" in body["error"]


def test_add_merchant_rejects_a_missing_phone_number(client, mock_db):
    status, body = graphql_request(client, ADD_MERCHANT, _valid_merchant_vars(phoneNumber=None))
    assert status == 400
    assert "phone number" in body["error"]


def test_add_merchant_rejects_a_duplicate_email(client, mock_db):
    mock_db.merchants.find_one.return_value = {"_id": ObjectId()}

    status, body = graphql_request(client, ADD_MERCHANT, _valid_merchant_vars())

    assert status == 400
    assert "already in use" in body["error"]


def test_add_merchant_returns_400_on_an_unexpected_error(client, mock_db):
    mock_db.merchants.find_one.side_effect = RuntimeError("boom")

    status, body = graphql_request(client, ADD_MERCHANT, _valid_merchant_vars())

    assert status == 400
    assert body["error"] == "Your request could not be processed. Please try again."


# --------------------------------------------------------------- merchantSearch


def test_merchant_search_requires_authentication(client):
    status, body = graphql_request(client, MERCHANT_SEARCH, {"search": "bob"})
    assert status == 401


def test_merchant_search_requires_the_admin_role(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Member"])

    status, body = graphql_request(client, MERCHANT_SEARCH, {"search": "bob"}, token)

    assert status == 403


def test_merchant_search_returns_matches_with_a_populated_brand_name(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Admin"])
    brand_id = ObjectId()
    mock_db.merchants.find.return_value = [{"_id": ObjectId(), "name": "Bob", "brand": brand_id}]
    mock_db.brands.find_one.return_value = {"name": "Bob's Brand"}

    status, body = graphql_request(client, MERCHANT_SEARCH, {"search": "bob"}, token)

    assert status == 200
    assert len(body["data"]["merchantSearch"]["merchants"]) == 1


def test_merchant_search_with_no_brand_on_a_merchant(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Admin"])
    mock_db.merchants.find.return_value = [{"_id": ObjectId(), "name": "Bob", "brand": None}]

    status, body = graphql_request(client, MERCHANT_SEARCH, {"search": "bob"}, token)

    assert status == 200
    assert body["data"]["merchantSearch"]["merchants"][0]["brand"] is None
    mock_db.brands.find_one.assert_not_called()


def test_merchant_search_with_no_search_value_still_works(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Admin"])
    mock_db.merchants.find.return_value = []

    status, body = graphql_request(client, MERCHANT_SEARCH, {}, token)

    assert status == 200
    assert body["data"]["merchantSearch"]["merchants"] == []


def test_merchant_search_returns_400_on_an_unexpected_error(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Admin"])
    mock_db.merchants.find.side_effect = RuntimeError("boom")

    status, body = graphql_request(client, MERCHANT_SEARCH, {"search": "bob"}, token)

    assert status == 400


# -------------------------------------------------------------------- merchants


def test_merchants_requires_authentication(client):
    status, body = graphql_request(client, MERCHANTS, {})
    assert status == 401


def test_merchants_requires_the_admin_role(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Merchant"])

    status, body = graphql_request(client, MERCHANTS, {}, token)

    assert status == 403


def test_merchants_lists_with_a_populated_brand(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Admin"])
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    brand_id = ObjectId()
    cursor.limit.return_value = [{"_id": ObjectId(), "name": "Bob", "brand": brand_id}]
    mock_db.merchants.find.return_value = cursor
    mock_db.merchants.count_documents.return_value = 1
    mock_db.brands.find_one.return_value = {"name": "Bob's Brand", "isActive": True}

    status, body = graphql_request(client, MERCHANTS, {"page": 1, "limit": 10}, token)

    assert status == 200
    assert body["data"]["merchants"]["count"] == 1


def test_merchants_with_no_brand_on_a_merchant(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Admin"])
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = [{"_id": ObjectId(), "name": "Bob", "brand": None}]
    mock_db.merchants.find.return_value = cursor
    mock_db.merchants.count_documents.return_value = 1

    status, body = graphql_request(client, MERCHANTS, {}, token)

    assert status == 200
    assert body["data"]["merchants"]["merchants"][0]["name"] == "Bob"


def test_merchants_returns_400_on_an_unexpected_error(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Admin"])
    mock_db.merchants.find.side_effect = RuntimeError("boom")

    status, body = graphql_request(client, MERCHANTS, {}, token)

    assert status == 400


# --------------------------------------------------------------- setMerchantActive


def test_set_merchant_active_requires_authentication(client):
    status, body = graphql_request(client, SET_MERCHANT_ACTIVE, {"merchantId": str(ObjectId()), "isActive": True})
    assert status == 401


def test_set_merchant_active_true_does_not_deactivate_the_brand(client, mock_db):
    user, token = _auth(mock_db)

    status, body = graphql_request(
        client, SET_MERCHANT_ACTIVE, {"merchantId": str(ObjectId()), "isActive": True}, token
    )

    assert status == 200
    mock_db.brands.find_one_and_update.assert_not_called()


def test_set_merchant_active_false_deactivates_the_brand(client, mock_db):
    user, token = _auth(mock_db)
    brand_id = ObjectId()
    mock_db.merchants.find_one.return_value = {"_id": ObjectId(), "brand": brand_id}

    status, body = graphql_request(
        client, SET_MERCHANT_ACTIVE, {"merchantId": str(ObjectId()), "isActive": False}, token
    )

    assert status == 200
    mock_db.brands.find_one_and_update.assert_called_once()


def test_set_merchant_active_false_with_no_existing_brand_is_a_no_op(client, mock_db):
    user, token = _auth(mock_db)
    mock_db.merchants.find_one.return_value = {"_id": ObjectId(), "brand": None}

    status, body = graphql_request(
        client, SET_MERCHANT_ACTIVE, {"merchantId": str(ObjectId()), "isActive": False}, token
    )

    assert status == 200
    mock_db.brands.find_one_and_update.assert_not_called()


def test_set_merchant_active_false_with_no_matching_merchant_is_a_no_op(client, mock_db):
    user, token = _auth(mock_db)
    mock_db.merchants.find_one.return_value = None

    status, body = graphql_request(
        client, SET_MERCHANT_ACTIVE, {"merchantId": str(ObjectId()), "isActive": False}, token
    )

    assert status == 200
    mock_db.brands.find_one_and_update.assert_not_called()


def test_set_merchant_active_returns_400_on_a_malformed_id(client, mock_db):
    user, token = _auth(mock_db)

    status, body = graphql_request(
        client, SET_MERCHANT_ACTIVE, {"merchantId": "not-an-id", "isActive": False}, token
    )

    assert status == 400


# ------------------------------------------------------------------ approveMerchant


def test_approve_merchant_requires_authentication(client):
    status, body = graphql_request(client, APPROVE_MERCHANT, {"merchantId": str(ObjectId())})
    assert status == 401


def test_approve_merchant_creates_a_new_user_for_a_first_time_merchant(client, mock_db):
    user, token = _auth(mock_db)
    merchant_id = ObjectId()
    mock_db.merchants.find_one_and_update.return_value = {
        "_id": merchant_id,
        "email": "new@merchant.com",
        "name": "New Merchant",
    }
    mock_db.users.find_one.side_effect = [user, None]  # auth lookup, then _create_merchant_user's lookup
    mock_db.users.insert_one.return_value.inserted_id = ObjectId()

    status, body = graphql_request(client, APPROVE_MERCHANT, {"merchantId": str(merchant_id)}, token)

    assert status == 200
    mock_db.users.insert_one.assert_called_once()


def test_approve_merchant_updates_an_existing_user_and_creates_the_brand(client, mock_db):
    user, token = _auth(mock_db)
    merchant_id = ObjectId()
    existing_user = {"_id": ObjectId()}
    mock_db.merchants.find_one_and_update.return_value = {
        "_id": merchant_id,
        "email": "existing@merchant.com",
        "name": "Existing Merchant",
    }
    mock_db.users.find_one.side_effect = [user, existing_user]
    mock_db.merchants.find_one.return_value = {
        "_id": merchant_id,
        "email": "existing@merchant.com",
        "brandName": "Brand",
        "business": "Business",
    }
    mock_db.brands.insert_one.return_value.inserted_id = ObjectId()

    status, body = graphql_request(client, APPROVE_MERCHANT, {"merchantId": str(merchant_id)}, token)

    assert status == 200
    mock_db.brands.insert_one.assert_called_once()
    mock_db.users.find_one_and_update.assert_called_once()


def test_approve_merchant_returns_400_on_an_unexpected_error(client, mock_db):
    user, token = _auth(mock_db)
    mock_db.merchants.find_one_and_update.return_value = None

    status, body = graphql_request(client, APPROVE_MERCHANT, {"merchantId": str(ObjectId())}, token)

    assert status == 400


# ------------------------------------------------------------------- rejectMerchant


def test_reject_merchant_requires_authentication(client):
    status, body = graphql_request(client, REJECT_MERCHANT, {"merchantId": str(ObjectId())})
    assert status == 401


def test_reject_merchant_succeeds(client, mock_db):
    user, token = _auth(mock_db)

    status, body = graphql_request(client, REJECT_MERCHANT, {"merchantId": str(ObjectId())}, token)

    assert status == 200
    assert body["data"]["rejectMerchant"]["success"] is True


def test_reject_merchant_returns_400_on_a_malformed_id(client, mock_db):
    user, token = _auth(mock_db)

    status, body = graphql_request(client, REJECT_MERCHANT, {"merchantId": "not-an-id"}, token)

    assert status == 400


# ------------------------------------------------------------------ merchantSignup


def test_merchant_signup_does_not_require_authentication(client, mock_db):
    mock_db.users.find_one.return_value = {"_id": ObjectId()}
    mock_db.merchants.find_one.return_value = {
        "_id": ObjectId(),
        "email": "a@test.com",
        "brandName": "Brand",
        "business": "Business",
    }
    mock_db.brands.insert_one.return_value.inserted_id = ObjectId()

    status, body = graphql_request(
        client,
        MERCHANT_SIGNUP,
        {"token": "sometoken", "email": "a@test.com", "firstName": "A", "lastName": "B", "password": "secret123"},
    )

    assert status == 200
    assert body["data"]["merchantSignup"]["success"] is True


def test_merchant_signup_rejects_a_missing_email(client, mock_db):
    status, body = graphql_request(
        client, MERCHANT_SIGNUP, {"token": "t", "firstName": "A", "lastName": "B", "password": "secret123"}
    )
    assert status == 400
    assert "email" in body["error"]


def test_merchant_signup_rejects_a_missing_name(client, mock_db):
    status, body = graphql_request(
        client, MERCHANT_SIGNUP, {"token": "t", "email": "a@test.com", "password": "secret123"}
    )
    assert status == 400
    assert "full name" in body["error"]


def test_merchant_signup_rejects_a_missing_password(client, mock_db):
    status, body = graphql_request(
        client, MERCHANT_SIGNUP, {"token": "t", "email": "a@test.com", "firstName": "A", "lastName": "B"}
    )
    assert status == 400
    assert "password" in body["error"]


def test_merchant_signup_returns_400_on_an_unexpected_error(client, mock_db):
    mock_db.users.find_one.return_value = None  # user_doc["_id"] then raises TypeError

    status, body = graphql_request(
        client,
        MERCHANT_SIGNUP,
        {"token": "t", "email": "a@test.com", "firstName": "A", "lastName": "B", "password": "secret123"},
    )

    assert status == 400
    assert body["error"] == "Your request could not be processed. Please try again."


# ------------------------------------------------------------------- deleteMerchant


def test_delete_merchant_requires_authentication(client):
    status, body = graphql_request(client, DELETE_MERCHANT, {"merchantId": str(ObjectId())})
    assert status == 401


def test_delete_merchant_requires_the_admin_role(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Member"])

    status, body = graphql_request(client, DELETE_MERCHANT, {"merchantId": str(ObjectId())}, token)

    assert status == 403


def test_delete_merchant_succeeds(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Admin"])
    mock_db.merchants.find_one.return_value = None
    mock_db.merchants.delete_one.return_value.deleted_count = 1

    status, body = graphql_request(client, DELETE_MERCHANT, {"merchantId": str(ObjectId())}, token)

    assert status == 200
    assert body["data"]["deleteMerchant"]["deletedCount"] == 1


def test_delete_merchant_returns_400_on_a_malformed_id(client, mock_db):
    user, token = _auth(mock_db, role=ROLES["Admin"])

    status, body = graphql_request(client, DELETE_MERCHANT, {"merchantId": "not-an-id"}, token)

    assert status == 400
