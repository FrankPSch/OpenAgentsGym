"""The pipeline: validate, price, allocate, and collect the result."""

from collections import namedtuple

from warehouse.feeds.money import round_half_away
from warehouse.rules.pricing import discount_band, line_total, tax_for
from warehouse.rules.stock import allocate
from warehouse.rules.validation import validate_order

HANDLING_FEE = 490
HANDLING_BELOW = 2000

Result = namedtuple("Result", "lines totals backorders rejects")


def process_orders(prices, orders, stock):
    """Price and allocate the accepted orders; return a Result."""
    reasons = {order.order_id: validate_order(order, prices) for order in orders}
    rejects = [(o.order_id, reasons[o.order_id]) for o in orders if reasons[o.order_id]]
    accepted = [o for o in orders if not reasons[o.order_id]]
    lines, totals = [], {}
    for order in sorted(accepted, key=lambda o: (o.placed, o.order_id)):
        rows = [prices[line.sku] for line in order.lines]
        nets = [line_total(row, line.qty) for row, line in zip(rows, order.lines)]
        percent = discount_band(sum(nets))
        cuts = [round_half_away(net * percent / 100.0) for net in nets]
        after = sum(nets) - sum(cuts)
        fee = HANDLING_FEE if after < HANDLING_BELOW else 0
        tax = sum(tax_for(row, net - cut) for row, net, cut in zip(rows, nets, cuts))
        lines += [(order.order_id, line.sku, -(-line.qty // row.pack_size) * row.pack_size, net)
                  for row, line, net in zip(rows, order.lines, nets)]
        totals[order.order_id] = {"net": sum(nets), "discount": sum(cuts), "handling": fee,
                                  "tax": tax, "gross": after + fee + tax}
    return Result(lines, totals, allocate(accepted, stock, prices)[1], rejects)
