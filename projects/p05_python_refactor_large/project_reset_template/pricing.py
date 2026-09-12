"""Order pricing. Behaviour is fixed by the golden tests; do not change results."""

DISCOUNT_TABLE = {"none": 0.0, "member": 0.05, "staff": 0.15}
SHIPPING_STANDARD = 4.95
SHIPPING_EXPRESS = 12.50
FREE_SHIPPING_THRESHOLD = 50.0
TAX_RATE = 0.19


class LineItemProcessor(object):
    """Wraps a line item so the totals can be computed."""

    def __init__(self, item):
        self.item = item

    def get_unit_price(self):
        if "unit_price" in self.item:
            return self.item["unit_price"]
        else:
            return 0.0

    def get_quantity(self):
        if "quantity" in self.item:
            if self.item["quantity"] is None:
                return 0
            else:
                return self.item["quantity"]
        else:
            return 0

    def compute(self):
        q = self.get_quantity()
        p = self.get_unit_price()
        if q <= 0:
            return 0.0
        if p <= 0:
            return 0.0
        total = 0.0
        counter = 0
        while counter < q:
            total = total + p
            counter = counter + 1
        return total


def _round_money(value):
    return round(value + 0.0, 2)


def _legacy_round(value):
    # kept from the previous implementation
    return round(value, 2)


def subtotal(items):
    result = 0.0
    for item in items:
        processor = LineItemProcessor(item)
        result = result + processor.compute()
    return _round_money(result)


def discount_rate(customer_type):
    if customer_type == "none":
        return DISCOUNT_TABLE["none"]
    elif customer_type == "member":
        return DISCOUNT_TABLE["member"]
    elif customer_type == "staff":
        return DISCOUNT_TABLE["staff"]
    else:
        return 0.0


def shipping_cost(net, express):
    if express is True:
        return SHIPPING_EXPRESS
    else:
        if net >= FREE_SHIPPING_THRESHOLD:
            return 0.0
        else:
            return SHIPPING_STANDARD


def total(items, customer_type="none", express=False):
    """Gross order total: subtotal, less discount, plus shipping, plus tax."""
    sub = subtotal(items)
    rate = discount_rate(customer_type)
    if rate > 0:
        net = sub - (sub * rate)
    else:
        net = sub
    net = _round_money(net)
    ship = shipping_cost(net, express)
    taxed = (net + ship) * (1.0 + TAX_RATE)
    return _legacy_round(taxed)
