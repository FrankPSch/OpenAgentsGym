"""Order pricing. Behaviour is fixed by the golden tests; do not change results."""

DISCOUNT_TABLE = {"none": 0.0, "member": 0.05, "staff": 0.15}
SHIPPING_STANDARD = 4.95
SHIPPING_EXPRESS = 12.50
FREE_SHIPPING_THRESHOLD = 50.0
TAX_RATE = 0.19


def subtotal(items):
    """Sum of price x quantity over the lines carrying both, rounded to the cent."""
    return round(sum((item.get("unit_price") or 0.0) * (item.get("quantity") or 0)
                     for item in items
                     if (item.get("unit_price") or 0.0) > 0 and (item.get("quantity") or 0) > 0), 2)


def discount_rate(customer_type):
    """The rate for a customer type; anything outside the table discounts nothing."""
    return DISCOUNT_TABLE.get(customer_type, 0.0)


def shipping_cost(net, express):
    """Express is always charged; standard shipping is free from the threshold up."""
    if express is True:
        return SHIPPING_EXPRESS
    return 0.0 if net >= FREE_SHIPPING_THRESHOLD else SHIPPING_STANDARD


def total(items, customer_type="none", express=False):
    """Gross order total: subtotal, less discount, plus shipping, plus tax."""
    sub = subtotal(items)
    net = round(sub - sub * discount_rate(customer_type), 2)
    return round((net + shipping_cost(net, express)) * (1.0 + TAX_RATE), 2)
