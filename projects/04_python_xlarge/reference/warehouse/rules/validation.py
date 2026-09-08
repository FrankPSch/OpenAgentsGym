"""Rejection reasons for an order that cannot be priced."""

from datetime import datetime


def validate_order(order, prices):
    """Return the list of rejection reasons; empty when the order is valid."""
    reasons = []
    try:
        datetime.strptime(order.placed, "%Y-%m-%d")
    except ValueError:
        reasons.append("unparsable date: %s" % order.placed)
    for line in order.lines:
        if line.sku not in prices:
            reasons.append("unknown sku: %s" % line.sku)
        if line.qty <= 0:
            reasons.append("non-positive qty: %s" % line.sku)
    return reasons
