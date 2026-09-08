"""Line pricing: whole packs, the discount bands, the tax classes."""

TAX_RATES = {"standard": 19, "reduced": 7, "zero": 0}


def line_total(row, qty):
    """Return the net of one line in cents, billing whole packs."""
    raise NotImplementedError


def discount_band(net):
    """Return the discount percent for an order net in cents."""
    raise NotImplementedError


def tax_for(row, net):
    """Return the tax in cents on `net` for the row's tax class."""
    raise NotImplementedError
