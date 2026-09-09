"""GraphQL object/input types. Scalar fields (ids, totals, messages, flags)
are strongly typed; deeply nested/heterogeneous Mongo sub-documents (an
order's line items, each with a populated product and that product's
populated brand) use GenericScalar rather than a full type graph for every
possible nested shape — the same pragmatic choice PyMongo's own
schema-less design already makes for this service. Every resolver builds
these types explicitly (never returns a raw dict for graphene's default
resolver to introspect).

The top-level id field on every type is deliberately wired as `_id`
(`graphene.ID(name="_id")`), not GraphQL's usual bare `id` — client/'s
existing Order/Merchant reducers and components already read `order._id`/
`merchant._id` everywhere (a holdover from Mongoose's own `_id`), and
GenericScalar fields like `products`/`brand` pass their *nested* `_id` keys
through unchanged regardless. Keeping the top-level key the same avoids
touching every one of those call sites just to satisfy a GraphQL naming
convention neither this schema nor its one real caller benefits from.
"""
import graphene
from graphene.types.generic import GenericScalar


class CartItemInput(graphene.InputObjectType):
    product = graphene.ID(required=True)
    quantity = graphene.Int(required=True)
    price = graphene.Float(required=True)
    taxable = graphene.Boolean()


class AddCartPayload(graphene.ObjectType):
    success = graphene.Boolean()
    cart_id = graphene.String()


class SuccessPayload(graphene.ObjectType):
    success = graphene.Boolean()


class OrderRefType(graphene.ObjectType):
    id = graphene.ID(name="_id")


class PlaceOrderPayload(graphene.ObjectType):
    success = graphene.Boolean()
    message = graphene.String()
    order = graphene.Field(OrderRefType)


class UpdateOrderItemStatusPayload(graphene.ObjectType):
    success = graphene.Boolean()
    order_cancelled = graphene.Boolean()
    message = graphene.String()


class OrderType(graphene.ObjectType):
    id = graphene.ID(name="_id")
    total = graphene.Float()
    total_tax = graphene.Float()
    total_with_tax = graphene.Float()
    created = graphene.String()
    cart_id = graphene.ID()
    # List of { _id, product: {..., brand: {...}}, quantity, status,
    # totalPrice, totalTax, priceWithTax, purchasePrice } — see store.py's
    # calculate_tax_amount/format_orders, which build this shape.
    products = GenericScalar()


class OrderListType(graphene.ObjectType):
    orders = graphene.List(OrderType)
    total_pages = graphene.Int()
    current_page = graphene.Int()
    count = graphene.Int()


class OrderSearchType(graphene.ObjectType):
    orders = graphene.List(OrderType)


class MerchantType(graphene.ObjectType):
    id = graphene.ID(name="_id")
    name = graphene.String()
    email = graphene.String()
    phone_number = graphene.String()
    brand_name = graphene.String()
    business = graphene.String()
    is_active = graphene.Boolean()
    status = graphene.String()
    created = graphene.String()
    # A populated Brand document (or just {name} for the search listing) or
    # null — see resolvers/merchant.py's _populate_brand/_populate_brand_name.
    brand = GenericScalar()


class AddMerchantPayload(graphene.ObjectType):
    success = graphene.Boolean()
    message = graphene.String()
    merchant = graphene.Field(MerchantType)


class MerchantListType(graphene.ObjectType):
    merchants = graphene.List(MerchantType)
    total_pages = graphene.Int()
    current_page = graphene.Int()
    count = graphene.Int()


class MerchantSearchType(graphene.ObjectType):
    merchants = graphene.List(MerchantType)


class DeleteMerchantPayload(graphene.ObjectType):
    success = graphene.Boolean()
    message = graphene.String()
    deleted_count = graphene.Int()
