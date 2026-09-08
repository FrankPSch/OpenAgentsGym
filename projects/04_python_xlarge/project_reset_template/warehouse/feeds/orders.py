"""Reader for the JSON order feed; the fixture defines the format."""

from collections import namedtuple

FEED_VERSION = 2

OrderLine = namedtuple("OrderLine", "sku qty")
Order = namedtuple("Order", "order_id customer placed lines")


def load_orders(path):
    """Read the order feed; return a list of Order in feed order."""
    raise NotImplementedError
