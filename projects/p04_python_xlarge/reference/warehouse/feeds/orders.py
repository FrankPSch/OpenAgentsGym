"""Reader for the JSON order feed; the fixture defines the format."""

import json
from collections import namedtuple

from warehouse import FeedError

FEED_VERSION = 2

OrderLine = namedtuple("OrderLine", "sku qty")
Order = namedtuple("Order", "order_id customer placed lines")


def _line(raw):
    """Build an OrderLine from one raw line object of the feed."""
    if "sku" not in raw or not isinstance(raw.get("qty"), int):
        raise FeedError("an order line needs a sku and an integer qty: %r" % (raw,))
    return OrderLine(str(raw["sku"]), raw["qty"])


def load_orders(path):
    """Read the order feed; return a list of Order in feed order."""
    with open(str(path), encoding="utf-8") as handle:
        feed = json.load(handle)
    if feed.get("feed_version") != FEED_VERSION:
        raise FeedError("feed_version must be %s" % FEED_VERSION)
    return [Order(str(raw["order_id"]), str(raw.get("customer", "")), str(raw["placed"]),
                  [_line(line) for line in raw.get("lines", [])])
            for raw in feed.get("orders", [])]
