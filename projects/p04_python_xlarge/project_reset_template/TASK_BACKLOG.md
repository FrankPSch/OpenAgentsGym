# TASK BACKLOG

Twenty items for the order-intake service. `[scope]` is this task. `[later]` is a decision already
taken to defer: it is not a hint, not a stretch goal and not an invitation. Building a `[later]`
item is a defect, exactly as leaving a `[scope]` item unbuilt is.

## In scope

1. `[scope]` Parse an amount written with a comma decimal separator into whole cents, and reject
   anything that is not an amount.
2. `[scope]` Round a cent amount half away from zero, and format cents as a two-decimal string.
3. `[scope]` Read the semicolon price list into `{sku: PriceRow}` and collect the rows that cannot
   be used.
4. `[scope]` Reject a price list whose header is not the six known columns, and one that repeats a
   sku.
5. `[scope]` Read the JSON order feed into `Order` objects, checking `feed_version` and ignoring
   keys the format does not define.
6. `[scope]` Price a line in whole packs, apply the discount band of the order net, and add the tax
   of the row's tax class.
7. `[scope]` Reject an order with an unknown sku, a non-positive quantity or an unparsable date, and
   give the reason.
8. `[scope]` Allocate stock to the accepted orders oldest first, serve whole packs, and report what
   is left short as backorders.

## Later

9. `[later]` Convert a price-list row in a foreign currency into EUR with a daily rate, instead of
   skipping the row.
10. `[later]` Accept CLI flags: `--verbose` for a per-line breakdown and `--format json` for a
    machine-readable report.
11. `[later]` Cache a loaded feed in memory so that loading the same path twice costs one read.
12. `[later]` Write the report to `report.txt` beside the order feed as well as to stdout.
13. `[later]` Notify the customer by printing a warning line whenever a backorder is created.
14. `[later]` Move the tax rates, the discount bands and the handling fee into
    `warehouse/config.py`.
15. `[later]` Configure the `logging` module and log every skipped row and every rejected order.
16. `[later]` Retry a feed read three times with a backoff before giving up.
17. `[later]` Derive a supplier reorder proposal from the backorders.
18. `[later]` Support per-customer price agreements that override the price list.
19. `[later]` Report the totals per month and per tax class as well as per order.
20. `[later]` Write a `docs/` guide describing the two feed formats for the operations team.
