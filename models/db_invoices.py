from models.database import DBModel


class Invoice(DBModel):
    STARTED = "started"
    SENT = "SENT"
    PRE_CHECKOUT = "pre_checkout"
    SUCCESS = "success"
    REFUND = "refund"

    Fields = {
        "user_id": ["INTEGER", 0],
        "shop_item_id": ["TEXT", ""],
        "invoice_status": ["TEXT", ""],
        "charge_id": ["TEXT", ""],
        "shop_type": ["TEXT", ""],
    }

    def __init__(self, id, user_id, shop_item_id, invoice_status, charge_id, shop_type):
        self.id = id
        self.user_id = user_id
        self.shop_item_id = shop_item_id
        self.invoice_status = invoice_status
        self.charge_id = charge_id
        self.shop_type = shop_type
