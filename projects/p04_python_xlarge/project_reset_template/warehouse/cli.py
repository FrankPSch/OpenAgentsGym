"""Command line entry point: read the two feeds, print the report."""

from warehouse.feeds.money import format_money
from warehouse.feeds.orders import load_orders
from warehouse.feeds.pricelist import load_pricelist
from warehouse.pipeline import process_orders


def main(argv):
    """Print the report for the price list and order feed named in argv; return the exit code."""
    raise NotImplementedError
