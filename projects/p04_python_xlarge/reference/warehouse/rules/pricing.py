"""Line pricing: whole packs, the discount bands, the tax classes."""

from warehouse.feeds.money import round_half_away

TAX_RATES = {"standard": 19, "reduced": 7, "zero": 0}
BANDS = ((200000, 8), (50000, 5), (10000, 3))


def line_total(row, qty):
    """Return the net of one line in cents, billing whole packs."""
    packs = -(-max(qty, 0) // row.pack_size)
    return packs * row.pack_size * row.unit_price


def discount_band(net):
    """Return the discount percent for an order net in cents."""
    for threshold, percent in BANDS:
        if net >= threshold:
            return percent
    return 0


def tax_for(row, net):
    """Return the tax in cents on `net` for the row's tax class."""
    return round_half_away(net * TAX_RATES[row.tax_class] / 100.0)
