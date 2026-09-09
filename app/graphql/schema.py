"""Assembles every Query/Mutation field from resolvers/{cart,order,merchant}.py
into the single schema served at POST /api/graphql — the GraphQL analogue
of routes/api/index.js fanning out to one router per resource, except every
resource lands on one schema instead of one mount prefix each.
"""
import graphene
from graphene.types.generic import GenericScalar

from .resolvers import cart as cart_resolvers
from .resolvers import merchant as merchant_resolvers
from .resolvers import order as order_resolvers
from .types import (
    AddCartPayload,
    AddMerchantPayload,
    CartItemInput,
    DeleteMerchantPayload,
    MerchantListType,
    MerchantSearchType,
    OrderListType,
    OrderSearchType,
    OrderType,
    PlaceOrderPayload,
    SuccessPayload,
    UpdateOrderItemStatusPayload,
)


class Query(graphene.ObjectType):
    order = graphene.Field(OrderType, id=graphene.ID(required=True))
    orders = graphene.Field(OrderListType, page=graphene.Int(), limit=graphene.Int())
    my_orders = graphene.Field(OrderListType, page=graphene.Int(), limit=graphene.Int())
    order_search = graphene.Field(OrderSearchType, search=graphene.String())

    merchants = graphene.Field(MerchantListType, page=graphene.Int(), limit=graphene.Int())
    merchant_search = graphene.Field(MerchantSearchType, search=graphene.String())

    resolve_order = staticmethod(order_resolvers.resolve_order)
    resolve_orders = staticmethod(order_resolvers.resolve_orders)
    resolve_my_orders = staticmethod(order_resolvers.resolve_my_orders)
    resolve_order_search = staticmethod(order_resolvers.resolve_order_search)

    resolve_merchants = staticmethod(merchant_resolvers.resolve_merchants)
    resolve_merchant_search = staticmethod(merchant_resolvers.resolve_merchant_search)


class Mutation(graphene.ObjectType):
    add_cart = graphene.Field(AddCartPayload, products=graphene.List(CartItemInput, required=True))
    delete_cart = graphene.Field(SuccessPayload, cart_id=graphene.ID(required=True))
    # GenericScalar (not a typed CartItemInput) — mirrors the original REST
    # add_item route, which pushed whatever object the caller sent straight
    # into the cart's products array with no validation at all.
    add_cart_item = graphene.Field(
        SuccessPayload, cart_id=graphene.ID(required=True), product=GenericScalar(required=True)
    )
    remove_cart_item = graphene.Field(
        SuccessPayload, cart_id=graphene.ID(required=True), product_id=graphene.ID(required=True)
    )

    place_order = graphene.Field(
        PlaceOrderPayload, cart_id=graphene.ID(required=True), total=graphene.Float()
    )
    cancel_order = graphene.Field(SuccessPayload, order_id=graphene.ID(required=True))
    update_order_item_status = graphene.Field(
        UpdateOrderItemStatusPayload,
        item_id=graphene.ID(required=True),
        order_id=graphene.ID(),
        cart_id=graphene.ID(),
        status=graphene.String(),
    )

    add_merchant = graphene.Field(
        AddMerchantPayload,
        name=graphene.String(),
        email=graphene.String(),
        phone_number=graphene.String(),
        brand_name=graphene.String(),
        business=graphene.String(),
    )
    set_merchant_active = graphene.Field(
        SuccessPayload, merchant_id=graphene.ID(required=True), is_active=graphene.Boolean(required=True)
    )
    approve_merchant = graphene.Field(SuccessPayload, merchant_id=graphene.ID(required=True))
    reject_merchant = graphene.Field(SuccessPayload, merchant_id=graphene.ID(required=True))
    merchant_signup = graphene.Field(
        SuccessPayload,
        token=graphene.String(required=True),
        email=graphene.String(),
        first_name=graphene.String(),
        last_name=graphene.String(),
        password=graphene.String(),
    )
    delete_merchant = graphene.Field(DeleteMerchantPayload, merchant_id=graphene.ID(required=True))

    resolve_add_cart = staticmethod(cart_resolvers.resolve_add_cart)
    resolve_delete_cart = staticmethod(cart_resolvers.resolve_delete_cart)
    resolve_add_cart_item = staticmethod(cart_resolvers.resolve_add_cart_item)
    resolve_remove_cart_item = staticmethod(cart_resolvers.resolve_remove_cart_item)

    resolve_place_order = staticmethod(order_resolvers.resolve_place_order)
    resolve_cancel_order = staticmethod(order_resolvers.resolve_cancel_order)
    resolve_update_order_item_status = staticmethod(order_resolvers.resolve_update_order_item_status)

    resolve_add_merchant = staticmethod(merchant_resolvers.resolve_add_merchant)
    resolve_set_merchant_active = staticmethod(merchant_resolvers.resolve_set_merchant_active)
    resolve_approve_merchant = staticmethod(merchant_resolvers.resolve_approve_merchant)
    resolve_reject_merchant = staticmethod(merchant_resolvers.resolve_reject_merchant)
    resolve_merchant_signup = staticmethod(merchant_resolvers.resolve_merchant_signup)
    resolve_delete_merchant = staticmethod(merchant_resolvers.resolve_delete_merchant)


schema = graphene.Schema(query=Query, mutation=Mutation)
