"""Allocation of stock to orders, and the backorders that remain."""


def allocate(orders, stock, prices):
    """Serve orders from stock in whole packs; return (served, backorders)."""
    left, served, backorders = dict(stock), {}, {}
    for order in sorted(orders, key=lambda o: (o.placed, o.order_id)):
        got = {}
        for line in order.lines:
            row = prices.get(line.sku)
            if row is None:
                continue
            want = -(-max(line.qty, 0) // row.pack_size) * row.pack_size
            free = left[line.sku] if line.sku in left else want
            take = min(want, free // row.pack_size * row.pack_size)
            if line.sku in left:
                left[line.sku] -= take
            if take:
                got[line.sku] = got.get(line.sku, 0) + take
            if want - take:
                backorders[line.sku] = backorders.get(line.sku, 0) + want - take
        served[order.order_id] = got
    return served, backorders
