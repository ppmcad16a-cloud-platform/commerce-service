from unittest.mock import MagicMock

from bson import ObjectId

from app import db as db_module
from app.store import (
    calculate_items_sales_tax,
    calculate_order_total,
    calculate_tax_amount,
    disable_products,
    format_orders,
)


def test_disable_products_noop_when_empty(monkeypatch):
    fake_db = MagicMock()
    monkeypatch.setattr(db_module, "_db", fake_db)

    disable_products([])

    fake_db.products.bulk_write.assert_not_called()


def test_disable_products_bulk_writes_when_present(monkeypatch):
    fake_db = MagicMock()
    monkeypatch.setattr(db_module, "_db", fake_db)

    disable_products([{"_id": ObjectId()}])

    fake_db.products.bulk_write.assert_called_once()


def test_calculate_order_total_excludes_cancelled():
    order = {
        "products": [
            {"totalPrice": 100, "status": "Not processed"},
            {"totalPrice": 50, "status": "Cancelled"},
        ]
    }
    assert calculate_order_total(order) == 100


def test_calculate_tax_amount_missing_products_key_returns_unchanged():
    order = {"total": 5}
    result = calculate_tax_amount(order)
    assert result == {"total": 5, "totalTax": 0}


def test_calculate_tax_amount_empty_products_list():
    order = {"products": [], "total": 0}
    result = calculate_tax_amount(order)
    assert result["total"] == 0
    assert result["totalTax"] == 0
    assert result["totalWithTax"] == 0


def test_calculate_tax_amount_taxable_item_computes_tax():
    order = {
        "products": [
            {
                "purchasePrice": 100,
                "quantity": 2,
                "status": "Not processed",
                "priceWithTax": 0,
                "totalTax": 0,
                "product": {"taxable": True, "price": 999},
            }
        ],
        "total": 200,
    }
    result = calculate_tax_amount(order)
    # 100 * (5/100) * 100 * 2 quantity = 1000 -> but formula is price*(rate/100)*100*qty
    # taxRate=0.05 -> price*(0.05/100)*100 = price*0.05 = 5 per unit *2 = 10
    assert result["products"][0]["totalTax"] == 10
    assert result["totalTax"] == 10
    assert result["total"] == 200
    assert result["totalWithTax"] == 210


def test_calculate_tax_amount_falls_back_to_product_price_when_purchase_price_falsy():
    order = {
        "products": [
            {
                "purchasePrice": 0,
                "quantity": 1,
                "status": "Not processed",
                "priceWithTax": 0,
                "totalTax": 0,
                "product": {"taxable": False, "price": 42},
            }
        ],
        "total": 0,
    }
    result = calculate_tax_amount(order)
    assert result["products"][0]["purchasePrice"] == 42
    assert result["products"][0]["totalPrice"] == 42


def test_calculate_tax_amount_non_taxable_item_keeps_existing_tax():
    order = {
        "products": [
            {
                "purchasePrice": 10,
                "quantity": 1,
                "status": "Not processed",
                "priceWithTax": 0,
                "totalTax": 3,
                "product": {"taxable": False, "price": 10},
            }
        ],
        "total": 10,
    }
    result = calculate_tax_amount(order)
    assert result["totalTax"] == 3


def test_calculate_tax_amount_cancelled_item_skips_tax_accumulation():
    order = {
        "products": [
            {
                "purchasePrice": 10,
                "quantity": 1,
                "status": "Cancelled",
                "priceWithTax": 0,
                "totalTax": 0,
                "product": {"taxable": True, "price": 10},
            }
        ],
        "total": 10,
    }
    result = calculate_tax_amount(order)
    assert result["totalTax"] == 0
    # Only non-cancelled items count toward the recomputed total.
    assert result["total"] == 0


def test_calculate_tax_amount_item_with_no_product_dict():
    order = {
        "products": [
            {
                "purchasePrice": 5,
                "quantity": 1,
                "status": "Not processed",
                "priceWithTax": 0,
                "totalTax": 0,
                "product": None,
            }
        ],
        "total": 5,
    }
    result = calculate_tax_amount(order)
    assert result["totalTax"] == 0


def test_calculate_tax_amount_swallows_unexpected_exception():
    class Explode(dict):
        def get(self, key, default=None):
            if key == "products":
                raise RuntimeError("boom")
            return super().get(key, default)

    order = Explode(total=1)
    result = calculate_tax_amount(order)
    assert result is order


def test_calculate_items_sales_tax_taxable_item():
    items = [{"price": 100, "quantity": 2, "taxable": True}]
    result = calculate_items_sales_tax(items)
    assert result[0]["totalPrice"] == 200
    assert result[0]["totalTax"] == 10
    assert result[0]["priceWithTax"] == 210


def test_calculate_items_sales_tax_non_taxable_item():
    items = [{"price": 50, "quantity": 1, "taxable": False}]
    result = calculate_items_sales_tax(items)
    assert result[0]["totalPrice"] == 50
    assert result[0]["totalTax"] == 0
    assert result[0]["priceWithTax"] == 0


def test_format_orders_with_cart_and_products():
    orders = [
        {
            "_id": "o1",
            "total": 100,
            "created": "now",
            "cart": {
                "products": [
                    {
                        "purchasePrice": 10,
                        "quantity": 1,
                        "status": "Not processed",
                        "priceWithTax": 0,
                        "totalTax": 0,
                        "product": {"taxable": False},
                    }
                ]
            },
        }
    ]
    result = format_orders(orders)
    assert result[0]["totalTax"] == 0
    assert "products" in result[0]


def test_format_orders_with_empty_products_list_still_taxed():
    orders = [{"_id": "o1", "total": 0, "created": "now", "cart": {"products": []}}]
    result = format_orders(orders)
    # Empty list is truthy-for-this-check (matches JS []-is-truthy), so tax
    # calc still runs (harmlessly) rather than being skipped.
    assert result[0]["totalTax"] == 0


def test_format_orders_with_missing_cart():
    orders = [{"_id": "o1", "total": 5, "created": "now"}]
    result = format_orders(orders)
    assert result[0]["products"] is None
    assert "totalTax" not in result[0]
