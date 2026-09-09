# Mirrors constants/index.js's exports across every microservice in this
# project — the exact string values are stored in MongoDB and shared
# between Python, Java, and Node services, so they must match byte-for-byte.

ROLES = {
    "Admin": "ROLE ADMIN",
    "Member": "ROLE MEMBER",
    "Merchant": "ROLE MERCHANT",
}

MERCHANT_STATUS = {
    "Rejected": "Rejected",
    "Approved": "Approved",
    "Waiting_Approval": "Waiting Approval",
}

CART_ITEM_STATUS = {
    "Processing": "Processing",
    "Shipped": "Shipped",
    "Delivered": "Delivered",
    "Cancelled": "Cancelled",
    "Not_processed": "Not processed",
}

# Needed by the trimmed User document shape's `provider` default.
EMAIL_PROVIDER = {
    "Email": "Email",
}
