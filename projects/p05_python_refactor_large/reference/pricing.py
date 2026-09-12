"""Order pricing. Behaviour is fixed by the golden tests; do not change results."""

DISCOUNT_TABLE = {"none": 0.0, "member": 0.05, "staff": 0.15}
SHIPPING_STANDARD = 4.95
SHIPPING_EXPRESS = 12.50
FREE_SHIPPING_THRESHOLD = 50.0
TAX_RATE = 0.19


def _line_total(unit_price, quantity):
    """One line: the unit price accumulated once per unit, as the pinned behaviour does."""
    # Not price * quantity: 0.001 fifteen times is 0.015000000000000003 and rounds to 0.02, the
    # product 0.015 rounds to 0.01. The accumulation is behaviour, so it is kept.
    line, counted = 0.0, 0
    while counted < quantity:
        line, counted = line + unit_price, counted + 1
    return line


def subtotal(items):
    """Sum of the lines carrying a positive price and quantity, rounded to the cent."""
    return round(sum(_line_total(item.get("unit_price") or 0.0, item.get("quantity") or 0)
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
