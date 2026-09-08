"""Command line entry point: read the two feeds, print the report."""

from warehouse.feeds.money import format_money
from warehouse.feeds.orders import load_orders
from warehouse.feeds.pricelist import load_pricelist
from warehouse.pipeline import process_orders


def main(argv):
    """Print the report for the price list and order feed named in argv; return the exit code."""
    if len(argv) != 2:
        return 2
    result = process_orders(load_pricelist(argv[0])[0], load_orders(argv[1]), {})
    report = ["ORDER;%s;%s" % (i, format_money(t["gross"])) for i, t in result.totals.items()]
    report += ["BACKORDER;%s;%d" % (s, result.backorders[s]) for s in sorted(result.backorders)]
    report += ["REJECT;%s;%s" % (i, r) for i, rs in result.rejects for r in rs]
    for line in report:
        print(line)
    return 0
