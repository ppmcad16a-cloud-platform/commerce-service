import math
import re
import secrets

import bcrypt
from bson import ObjectId

from ...auth import require_auth, require_role
from ...constants import MERCHANT_STATUS, ROLES
from ...db import get_db
from ...json_utils import to_jsonable
from ..errors import GENERIC_ERROR_MESSAGE, BadRequestError, GraphQLHttpError
from ..types import (
    AddMerchantPayload,
    DeleteMerchantPayload,
    MerchantListType,
    MerchantSearchType,
    MerchantType,
    SuccessPayload,
)


def _merchant_type(merchant):
    return MerchantType(
        id=str(merchant["_id"]),
        name=merchant.get("name"),
        email=merchant.get("email"),
        phone_number=merchant.get("phoneNumber"),
        brand_name=merchant.get("brandName"),
        business=merchant.get("business"),
        is_active=merchant.get("isActive"),
        status=merchant.get("status"),
        created=to_jsonable(merchant.get("created")),
        brand=to_jsonable(merchant.get("brand")),
    )


def resolve_add_merchant(root, info, name=None, email=None, phone_number=None, brand_name=None, business=None):
    try:
        if not name or not email:
            raise BadRequestError("You must enter your name and email.")

        if not business:
            raise BadRequestError("You must enter a business description.")

        if not phone_number or not email:
            raise BadRequestError("You must enter a phone number and an email address.")

        if get_db().merchants.find_one({"email": email}):
            raise BadRequestError("That email address is already in use.")

        merchant_doc = {
            "name": name,
            "email": email,
            "business": business,
            "phoneNumber": phone_number,
            "brandName": brand_name,
            "isActive": False,
            "brand": None,
            "status": MERCHANT_STATUS["Waiting_Approval"],
        }
        result = get_db().merchants.insert_one(merchant_doc)
        merchant_doc["_id"] = result.inserted_id

        return AddMerchantPayload(
            success=True,
            message=f"We received your request! we will reach you on your phone number {phone_number}!",
            merchant=_merchant_type(merchant_doc),
        )
    except GraphQLHttpError:
        raise
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_merchant_search(root, info, search=""):
    require_auth(info.context)
    require_role(info.context, ROLES["Admin"])
    try:
        pattern = re.compile(re.escape(search or ""), re.IGNORECASE)

        merchants = list(get_db().merchants.find({
            "$or": [
                {"phoneNumber": pattern},
                {"email": pattern},
                {"name": pattern},
                {"brandName": pattern},
                {"status": pattern},
            ]
        }))
        for merchant in merchants:
            merchant["brand"] = _populate_brand_name(merchant.get("brand"))

        return MerchantSearchType(merchants=[_merchant_type(m) for m in merchants])
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_merchants(root, info, page=1, limit=10):
    require_auth(info.context)
    require_role(info.context, ROLES["Admin"])
    try:
        cursor = (
            get_db()
            .merchants.find()
            .sort("created", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )
        merchants = list(cursor)
        for merchant in merchants:
            merchant["brand"] = _populate_brand(merchant.get("brand"))

        count = get_db().merchants.count_documents({})

        return MerchantListType(
            merchants=[_merchant_type(m) for m in merchants],
            total_pages=math.ceil(count / limit),
            current_page=page,
            count=count,
        )
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_set_merchant_active(root, info, merchant_id, is_active):
    require_auth(info.context)
    try:
        get_db().merchants.find_one_and_update(
            {"_id": ObjectId(merchant_id)}, {"$set": {"isActive": is_active}}, return_document=True
        )

        if not is_active:
            _deactivate_brand(merchant_id)

        return SuccessPayload(success=True)
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_approve_merchant(root, info, merchant_id):
    require_auth(info.context)
    try:
        update = {"status": MERCHANT_STATUS["Approved"], "isActive": True}
        merchant_doc = get_db().merchants.find_one_and_update(
            {"_id": ObjectId(merchant_id)}, {"$set": update}, return_document=True
        )

        _create_merchant_user(merchant_doc["email"], merchant_doc["name"], merchant_doc["_id"])

        return SuccessPayload(success=True)
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_reject_merchant(root, info, merchant_id):
    require_auth(info.context)
    try:
        update = {"status": MERCHANT_STATUS["Rejected"]}
        get_db().merchants.find_one_and_update(
            {"_id": ObjectId(merchant_id)}, {"$set": update}, return_document=True
        )

        return SuccessPayload(success=True)
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_merchant_signup(root, info, token, email=None, first_name=None, last_name=None, password=None):
    try:
        if not email:
            raise BadRequestError("You must enter an email address.")

        if not first_name or not last_name:
            raise BadRequestError("You must enter your full name.")

        if not password:
            raise BadRequestError("You must enter a password.")

        user_doc = get_db().users.find_one({
            "email": email,
            "resetPasswordToken": token,
        })

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10))

        get_db().users.find_one_and_update(
            {"_id": user_doc["_id"]},
            {
                "$set": {
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                    "password": hashed.decode("utf-8"),
                },
                "$unset": {"resetPasswordToken": ""},
            },
            return_document=True,
        )

        merchant_doc = get_db().merchants.find_one({"email": email})
        _create_merchant_brand(merchant_doc)

        return SuccessPayload(success=True)
    except GraphQLHttpError:
        raise
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def resolve_delete_merchant(root, info, merchant_id):
    require_auth(info.context)
    require_role(info.context, ROLES["Admin"])
    try:
        _deactivate_brand(merchant_id)
        result = get_db().merchants.delete_one({"_id": ObjectId(merchant_id)})

        return DeleteMerchantPayload(
            success=True,
            message="Merchant has been deleted successfully!",
            deleted_count=result.deleted_count,
        )
    except Exception:
        raise BadRequestError(GENERIC_ERROR_MESSAGE)


def _deactivate_brand(merchant_id):
    merchant_doc = get_db().merchants.find_one({"_id": ObjectId(merchant_id)})
    if not merchant_doc or not merchant_doc.get("brand"):
        return None
    brand_id = merchant_doc["brand"]
    return get_db().brands.find_one_and_update(
        {"_id": brand_id}, {"$set": {"isActive": False}}, return_document=True
    )


def _create_merchant_brand(merchant_doc):
    new_brand = {
        "name": merchant_doc.get("brandName"),
        "description": merchant_doc.get("business"),
        "merchant": merchant_doc["_id"],
        "isActive": False,
    }
    result = get_db().brands.insert_one(new_brand)

    get_db().merchants.update_one(
        {"_id": merchant_doc["_id"]}, {"$set": {"brand": result.inserted_id}}
    )


def _create_merchant_user(email, name, merchant_id):
    first_name = name
    last_name = ""

    existing_user = get_db().users.find_one({"email": email})

    if existing_user:
        update = {"merchant": merchant_id, "role": ROLES["Merchant"]}

        merchant_doc = get_db().merchants.find_one({"email": email})
        _create_merchant_brand(merchant_doc)

        return get_db().users.find_one_and_update(
            {"_id": existing_user["_id"]}, {"$set": update}, return_document=True
        )

    reset_password_token = secrets.token_hex(48)

    user = {
        "email": email,
        "firstName": first_name,
        "lastName": last_name,
        "resetPasswordToken": reset_password_token,
        "merchant": merchant_id,
        "role": ROLES["Merchant"],
        "provider": "Email",
    }
    result = get_db().users.insert_one(user)
    user["_id"] = result.inserted_id
    return user


def _populate_brand_name(brand_id):
    if not isinstance(brand_id, ObjectId):
        return None
    return get_db().brands.find_one({"_id": brand_id}, {"name": 1})


def _populate_brand(brand_id):
    if not isinstance(brand_id, ObjectId):
        return None
    return get_db().brands.find_one({"_id": brand_id})
