from bson import ObjectId
from pymongo import UpdateOne

from ...auth import require_auth
from ...db import get_db
from ...store import calculate_items_sales_tax
from ..errors import GENERIC_ERROR_MESSAGE, BadRequestError
from ..types import AddCartPayload, SuccessPayload

# None of these resolvers raise a typed GraphQLHttpError from inside their
# own try block (require_auth already ran before it, and nothing else here
# needs a specific status/message) — so unlike resolvers/order.py's
# resolve_order or resolvers/merchant.py's resolve_add_merchant, there's no
# `except GraphQLHttpError: raise` here to preserve ahead of the generic
# fallback; every exception reaching these try blocks is unexpected.


def resolve_add_cart(root, info, products):
    require_auth(info.context)
    try:
        items = [dict(item) for item in products]
        items = calculate_items_sales_tax(items)

        # Match the CartItemSchema's defaults for a field this helper
        # doesn't set, and cast the client-supplied product id string to a
        # real ObjectId the way Mongoose's ref casting would.
        for item in items:
            item.setdefault("status", "Not processed")
            item["product"] = ObjectId(item["product"])

        cart_doc = {
            "user": info.context.current_user["_id"],
            "products": items,
        }
        result = get_db().carts.insert_one(cart_doc)

        # Fire-and-forget inventory decrement — same semantics as the
        # original's unawaited Product.bulkWrite: the response doesn't wait
        # on (or fail because of) this.
        _decrease_quantity(items)

        return AddCartPayload(success=True, cart_id=str(result.inserted_id))
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_delete_cart(root, info, cart_id):
    require_auth(info.context)
    try:
        get_db().carts.delete_one({"_id": ObjectId(cart_id)})
        return SuccessPayload(success=True)
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_add_cart_item(root, info, cart_id, product):
    require_auth(info.context)
    try:
        get_db().carts.update_one(
            {"_id": ObjectId(cart_id)}, {"$push": {"products": product}}
        )
        return SuccessPayload(success=True)
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_remove_cart_item(root, info, cart_id, product_id):
    require_auth(info.context)
    try:
        get_db().carts.update_one(
            {"_id": ObjectId(cart_id)},
            {"$pull": {"products": {"product": ObjectId(product_id)}}},
        )
        return SuccessPayload(success=True)
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def _decrease_quantity(products):
    ops = [
        UpdateOne({"_id": item["product"]}, {"$inc": {"quantity": -item["quantity"]}})
        for item in products
    ]
    if ops:
        get_db().products.bulk_write(ops)
