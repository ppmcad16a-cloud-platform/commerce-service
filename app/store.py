from pymongo import UpdateOne

from . import tax_config
from .db import get_db

# Port of utils/store.js, faithful to the original's JS-specific quirks
# (e.g. `x || y` treats 0 as falsy, matched here with Python's `or` which
# behaves the same way for numeric 0). One real language-semantics trap
# handled deliberately throughout: JS's `[]` is truthy, Python's is not —
# every `is not None` / `len(x) > 0` check below is written to avoid
# silently taking a different branch than the original for an
# empty-but-present list.


def disable_products(products):
    # Single early guard (unlike order.py's _increase_quantity/cart.py's
    # _decrease_quantity, which build `ops` unconditionally and guard the
    # bulk_write call itself) — kept as one reachable branch rather than two
    # equivalent ones, since `products` non-empty always implies `ops`
    # non-empty here (a 1:1 comprehension over it).
    if not products:
        return
    ops = [
        UpdateOne({"_id": item["_id"]}, {"$set": {"isActive": False}})
        for item in products
    ]
    get_db().products.bulk_write(ops)


def calculate_order_total(order):
    return sum(
        item.get("totalPrice", 0)
        for item in order.get("products", [])
        if item.get("status") != "Cancelled"
    )


def calculate_tax_amount(order):
    try:
        tax_rate = tax_config.STATE_TAX_RATE
        order["totalTax"] = 0

        products = order.get("products")
        if products and len(products) > 0:
            for item in products:
                product = item.get("product") or {}
                # `or` mirrors JS's `||`: a purchasePrice of exactly 0 falls
                # through to the product's live price, same as the original.
                price = item.get("purchasePrice") or product.get("price", 0)
                quantity = item.get("quantity")
                item["totalPrice"] = price * quantity
                item["purchasePrice"] = price

                if item.get("status") != "Cancelled":
                    if product.get("taxable") and item.get("priceWithTax") == 0:
                        tax_amount = price * (tax_rate / 100) * 100
                        item["totalTax"] = round(tax_amount * quantity, 2)
                        order["totalTax"] += item["totalTax"]
                    else:
                        order["totalTax"] += item.get("totalTax", 0)

                item["priceWithTax"] = round(item["totalPrice"] + item["totalTax"], 2)

        # Unguarded access, same as the original — if order["products"] is
        # missing entirely (no cart), this raises and falls into the
        # except-return-unchanged branch below, matching the JS behavior.
        has_cancelled_items = [
            item for item in order["products"] if item.get("status") == "Cancelled"
        ]
        if len(has_cancelled_items) > 0:
            order["total"] = calculate_order_total(order)

        current_total = calculate_order_total(order)
        if current_total != order.get("total"):
            order["total"] = calculate_order_total(order)

        order["totalWithTax"] = order.get("total", 0) + order["totalTax"]
        order["total"] = round(order.get("total", 0), 2)
        order["totalTax"] = round(order["totalTax"], 2) if order["totalTax"] else 0
        order["totalWithTax"] = round(order["totalWithTax"], 2)
        return order
    except Exception:
        return order


def calculate_items_sales_tax(items):
    tax_rate = tax_config.STATE_TAX_RATE

    result = []
    for item in items:
        item["priceWithTax"] = 0
        item["totalPrice"] = 0
        item["totalTax"] = 0
        item["purchasePrice"] = item.get("price")

        price = item["purchasePrice"]
        quantity = item.get("quantity")
        item["totalPrice"] = round(price * quantity, 2)

        if item.get("taxable"):
            tax_amount = price * (tax_rate / 100) * 100
            item["totalTax"] = round(tax_amount * quantity, 2)
            item["priceWithTax"] = round(item["totalPrice"] + item["totalTax"], 2)

        result.append(item)

    return result


def format_orders(orders):
    new_orders = []
    for order in orders:
        cart = order.get("cart") or {}
        new_orders.append(
            {
                "_id": order["_id"],
                "total": round(order.get("total", 0), 2),
                "created": order.get("created"),
                "products": cart.get("products"),
            }
        )

    # `is not None` (not plain truthiness) so an order whose cart legitimately
    # has zero line items still gets tax-calculated, same as the original
    # (where an empty JS array is truthy) — only a genuinely missing cart
    # (products is None) skips this.
    return [
        calculate_tax_amount(o) if o.get("products") is not None else o
        for o in new_orders
    ]
