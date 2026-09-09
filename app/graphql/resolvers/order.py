import math

import requests
from bson import ObjectId
from flask import current_app

from ...auth import require_auth
from ...constants import CART_ITEM_STATUS, ROLES
from ...db import get_db
from ...json_utils import to_jsonable
from ...store import calculate_tax_amount, format_orders
from ..errors import GENERIC_ERROR_MESSAGE, BadRequestError, GraphQLHttpError, NotFoundError
from ..types import (
    OrderListType,
    OrderRefType,
    OrderSearchType,
    OrderType,
    PlaceOrderPayload,
    SuccessPayload,
    UpdateOrderItemStatusPayload,
)


def _order_type(order):
    return OrderType(
        id=str(order["_id"]),
        total=order.get("total"),
        total_tax=order.get("totalTax"),
        total_with_tax=order.get("totalWithTax"),
        created=to_jsonable(order.get("created")),
        cart_id=str(order["cartId"]) if order.get("cartId") else None,
        products=to_jsonable(order.get("products")),
    )


def resolve_place_order(root, info, cart_id, total=None):
    require_auth(info.context)
    try:
        order_doc = {
            "cart": ObjectId(cart_id),
            "user": info.context.current_user["_id"],
            "total": total,
        }
        result = get_db().orders.insert_one(order_doc)

        # Fire-and-forget cross-service call to notification_server — a
        # failed (or mocked) confirmation email must never fail checkout
        # itself. Runs synchronously (same disclosed simplification as the
        # original REST version — Flask/this GraphQL view have no
        # equivalent of Node's non-blocking event-loop fire-and-forget
        # without extra thread bookkeeping); only response latency differs.
        try:
            _send_order_confirmation_email(result.inserted_id, info.context.current_user)
        except Exception as email_error:
            current_app.logger.info(
                "Failed to send order confirmation email: %s", email_error
            )

        return PlaceOrderPayload(
            success=True,
            message="Your order has been placed successfully!",
            order=OrderRefType(id=str(result.inserted_id)),
        )
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_order_search(root, info, search=None):
    require_auth(info.context)
    try:
        if not search or not ObjectId.is_valid(search):
            return OrderSearchType(orders=[])

        query = {"_id": ObjectId(search)}
        if info.context.current_user.get("role") != ROLES["Admin"]:
            query["user"] = info.context.current_user["_id"]

        orders_doc = list(get_db().orders.find(query))
        for order in orders_doc:
            order["cart"] = _populate_cart_products_brand(
                get_db().carts.find_one({"_id": order.get("cart")})
            )

        orders_doc = [o for o in orders_doc if o.get("cart")]

        if len(orders_doc) > 0:
            new_orders = [
                {
                    "_id": o["_id"],
                    "total": round(o.get("total", 0), 2),
                    "created": o.get("created"),
                    "products": o["cart"].get("products"),
                }
                for o in orders_doc
            ]
            orders = [calculate_tax_amount(o) for o in new_orders]
            orders.sort(key=lambda o: o.get("created"), reverse=True)
            return OrderSearchType(orders=[_order_type(o) for o in orders])

        return OrderSearchType(orders=[])
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_orders(root, info, page=1, limit=10):
    require_auth(info.context)
    try:
        cursor = (
            get_db()
            .orders.find()
            .sort("created", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )
        orders_doc = list(cursor)
        for order in orders_doc:
            order["cart"] = _populate_cart_products_brand(
                get_db().carts.find_one({"_id": order.get("cart")})
            )

        count = get_db().orders.count_documents({})
        orders = format_orders(orders_doc)

        return OrderListType(
            orders=[_order_type(o) for o in orders],
            total_pages=math.ceil(count / limit),
            current_page=page,
            count=count,
        )
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_my_orders(root, info, page=1, limit=10):
    require_auth(info.context)
    try:
        query = {"user": info.context.current_user["_id"]}

        cursor = (
            get_db()
            .orders.find(query)
            .sort("created", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )
        orders_doc = list(cursor)
        for order in orders_doc:
            order["cart"] = _populate_cart_products_brand(
                get_db().carts.find_one({"_id": order.get("cart")})
            )

        count = get_db().orders.count_documents(query)
        orders = format_orders(orders_doc)

        return OrderListType(
            orders=[_order_type(o) for o in orders],
            total_pages=math.ceil(count / limit),
            current_page=page,
            count=count,
        )
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_order(root, info, id):
    require_auth(info.context)
    try:
        query = {"_id": ObjectId(id)}
        if info.context.current_user.get("role") != ROLES["Admin"]:
            query["user"] = info.context.current_user["_id"]

        order_doc = get_db().orders.find_one(query)
        cart = None
        if order_doc:
            cart = _populate_cart_products_brand(
                get_db().carts.find_one({"_id": order_doc.get("cart")})
            )

        if not order_doc or not cart:
            raise NotFoundError(f"Cannot find order with the id: {id}.")

        order = {
            "_id": order_doc["_id"],
            "total": order_doc.get("total"),
            "created": order_doc.get("created"),
            "totalTax": 0,
            "products": cart.get("products"),
            "cartId": cart["_id"],
        }
        order = calculate_tax_amount(order)

        return _order_type(order)
    except GraphQLHttpError:
        raise
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_cancel_order(root, info, order_id):
    require_auth(info.context)
    try:
        order = get_db().orders.find_one({"_id": ObjectId(order_id)})
        found_cart = get_db().carts.find_one({"_id": order["cart"]})

        _increase_quantity(found_cart["products"])

        get_db().orders.delete_one({"_id": ObjectId(order_id)})
        get_db().carts.delete_one({"_id": order["cart"]})

        return SuccessPayload(success=True)
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_update_order_item_status(root, info, item_id, order_id=None, cart_id=None, status=None):
    require_auth(info.context)
    try:
        status = status or CART_ITEM_STATUS["Cancelled"]

        item_object_id = ObjectId(item_id)
        found_cart = get_db().carts.find_one({"products._id": item_object_id})
        found_cart_product = next(
            (p for p in found_cart["products"] if p["_id"] == item_object_id), None
        )

        get_db().carts.update_one(
            {"products._id": item_object_id},
            {"$set": {"products.$.status": status}},
        )

        if status == CART_ITEM_STATUS["Cancelled"]:
            get_db().products.update_one(
                {"_id": found_cart_product["product"]},
                {"$inc": {"quantity": found_cart_product["quantity"]}},
            )

            cart = get_db().carts.find_one({"_id": ObjectId(cart_id)})
            cancelled_items = [
                item
                for item in cart["products"]
                if item.get("status") == CART_ITEM_STATUS["Cancelled"]
            ]

            if len(cart["products"]) == len(cancelled_items):
                get_db().orders.delete_one({"_id": ObjectId(order_id)})
                get_db().carts.delete_one({"_id": ObjectId(cart_id)})

                who = (
                    "Order"
                    if info.context.current_user.get("role") == ROLES["Admin"]
                    else "Your order"
                )
                return UpdateOrderItemStatusPayload(
                    success=True,
                    order_cancelled=True,
                    message=f"{who} has been cancelled successfully",
                )

            return UpdateOrderItemStatusPayload(
                success=True,
                message="Item has been cancelled successfully!",
            )

        return UpdateOrderItemStatusPayload(
            success=True,
            message="Item status has been updated successfully!",
        )
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def _send_order_confirmation_email(order_id, user):
    order_doc = get_db().orders.find_one({"_id": order_id})
    if not order_doc:
        return

    cart = get_db().carts.find_one({"_id": order_doc.get("cart")})
    if not cart:
        return

    cart = _populate_cart_products(cart)

    order = {
        "_id": order_doc["_id"],
        "total": order_doc.get("total"),
        "created": order_doc.get("created"),
        "totalTax": 0,
        "products": cart.get("products"),
    }
    order = calculate_tax_amount(order)

    notification_url = current_app.config["NOTIFICATION_URL"]
    requests.post(
        f"{notification_url}/api/notification/order-confirmation",
        json=to_jsonable({"user": {"email": user.get("email")}, "order": order}),
        timeout=5,
    )


def _increase_quantity(products):
    from pymongo import UpdateOne

    ops = [
        UpdateOne({"_id": item["product"]}, {"$inc": {"quantity": item["quantity"]}})
        for item in products
    ]
    if ops:
        get_db().products.bulk_write(ops)


def _populate_cart_products(cart):
    """Mirrors `.populate({path:'cart', populate:{path:'products.product'}})`
    — replaces each line item's product id with the full product document."""
    if not cart:
        return cart
    db = get_db()
    for item in cart.get("products", []):
        product_id = item.get("product")
        if isinstance(product_id, ObjectId):
            item["product"] = db.products.find_one({"_id": product_id})
    return cart


def _populate_cart_products_brand(cart):
    """Mirrors the deeper populate chain
    `{path:'cart', populate:{path:'products.product', populate:{path:'brand'}}}`
    used by every order-listing query."""
    cart = _populate_cart_products(cart)
    if not cart:
        return cart
    db = get_db()
    for item in cart.get("products", []):
        product = item.get("product")
        if isinstance(product, dict):
            brand_id = product.get("brand")
            if isinstance(brand_id, ObjectId):
                product["brand"] = db.brands.find_one({"_id": brand_id})
    return cart
