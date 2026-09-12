"""The pipeline: validate, price, allocate, and collect the result."""

from collections import namedtuple

HANDLING_FEE = 490
HANDLING_BELOW = 2000

Result = namedtuple("Result", "lines totals backorders rejects")


def process_orders(prices, orders, stock):
    """Price and allocate the accepted orders; return a Result."""
    raise NotImplementedError
