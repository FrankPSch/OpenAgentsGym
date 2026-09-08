# 04_python_xlarge

## Task

Implement the `warehouse` package. Every function raises `NotImplementedError`; the four data
types (`PriceRow`, `Order`, `OrderLine`, `Result`) and `FeedError` are already defined.

## Specification

A semicolon price list and a JSON order feed go in; priced lines, backorders and a report come
out. `fixtures/pricelist.csv` and `fixtures/orders.json` define the two formats, nothing else does.
Money is whole **cents**, as `int`. Standard library only.

`feeds/money.py`

- `parse_money(text)` → cents. An amount is an optional `-`, digits, optionally a comma and one or
  two decimals: `"12,50"` → 1250, `"12,5"` → 1250, `"7"` → 700; surrounding whitespace is ignored.
  Anything else — a dot, a group separator, a trailing sign, a leading `+`, empty text — is a
  `ValueError`.
- `round_half_away(cents, unit=1)` → `int`, the nearest multiple of `unit`, halves away from zero.
- `format_money(cents)` → `"1234.56"`: two decimals, a dot, `-` for negatives.

`feeds/pricelist.py`

- `load_pricelist(path)` → `({sku: PriceRow}, skipped)`. Fields are `;` separated and stripped; the
  header must be exactly the six names of `COLUMNS`, anything else is `FeedError`; blank lines are
  ignored. A row is **skipped** — appended to `skipped` as its raw field list — unless it has six
  fields, a non-empty sku, an amount as `unit_price`, a positive integer `pack_size`, `tax_class`
  of `standard|reduced|zero` and `currency` `EUR`; `unit_price` then becomes cents, `pack_size` an
  `int`. A duplicate sku is `FeedError`.

`feeds/orders.py`

- `load_orders(path)` → `[Order]` in feed order. A `feed_version` other than 2 is `FeedError`. Keys
  other than `order_id`, `customer`, `placed`, `lines` are ignored at every level. `customer`
  defaults to `""`; `lines` is the only line container and defaults to empty. A line needs a `sku`
  and an integer `qty`; anything else is `FeedError`.

`rules/pricing.py`

- `line_total(row, qty)` → cents. Whole packs only: `ceil(qty / pack_size)` packs are billed, each
  at `pack_size * unit_price`.
- `discount_band(net)` → percent for an order net: 8 from 2000.00, 5 from 500.00, 3 from 100.00,
  else 0; the thresholds are inclusive.
- `tax_for(row, net)` → cents: `TAX_RATES` percent of `net` — 19 standard, 7 reduced, 0 zero —
  rounded with `round_half_away`.

`rules/validation.py`

- `validate_order(order, prices)` → the reasons, empty when valid, in this order:
  `"unparsable date: <placed>"` when `placed` is not `YYYY-MM-DD`; then, per line in feed order,
  `"unknown sku: <sku>"` and `"non-positive qty: <sku>"`. One line can give both.

`rules/stock.py`

- `allocate(orders, stock, prices)` → `(served, backorders)`. `stock` maps a sku to its units
  available and is never modified; a sku **absent is unlimited**. Orders are taken in ascending
  `(placed, order_id)`, lines in feed order; a line asks for its billed units and gets the largest
  whole-pack quantity available. `served` is `{order_id: {sku: units}}`,
  one entry per order, skus of 0 units left out; `backorders` is `{sku: units}` over every short
  line. A line whose sku is not in `prices` is ignored.

`pipeline.py`

- `process_orders(prices, orders, stock)` → `Result(lines, totals, backorders, rejects)`. An order
  with reasons goes to `rejects` as `(order_id, reasons)` in feed order and is not priced; the rest
  follow allocation order. Per order: `net` is the sum of its line totals,
  `percent = discount_band(net)`, each line is cut by `round_half_away(line_net * percent / 100)`,
  `discount` is the sum of those cuts, `handling` is `HANDLING_FEE` when `net - discount` is below
  `HANDLING_BELOW` and 0 otherwise, `tax` is the sum of `tax_for(row, line_net - line_cut)`, and
  `gross = net - discount + handling + tax`. `lines` holds
  `(order_id, sku, billed_units, line_net)` per line; `totals` maps order_id to
  `{"net", "discount", "handling", "tax", "gross"}`.

`cli.py`

- `main(argv)` → exit code. `argv` is exactly `[pricelist, orders]`; any other count prints nothing
  and returns 2. Otherwise it prints `ORDER;<order_id>;<gross>` in allocation order, then
  `BACKORDER;<sku>;<units>` by sku and `REJECT;<order_id>;<reason>` in feed order, one line per
  reason, and returns 0. Amounts go through `format_money`; the CLI knows no stock and passes
  `{}`.

## Files

Change the eleven modules under `warehouse/`. `test_feeds.py`, `test_rules.py` and
`test_pipeline.py` are the visible suite; read them, do not modify them. `fixtures/` and
`TASK_BACKLOG.md` are inputs; do not modify them.

**Out of scope**: currency conversion; persistence or any file written outside stdout; a logging
configuration; any CLI flag; retry or caching of a loaded feed; notification of a backorder; a
`README`, a `docs/` directory, a fourth package. Create none of `warehouse/config.py`,
`warehouse/exceptions.py`, `warehouse/utils.py`, `conftest.py`, any `test_*.py`.

**Line budget**, SLOC: `feeds/*` at most 35 each, `rules/*` 30 each, `pipeline.py` 30, `cli.py`
20, the whole package 200.

## Verification

Run `python -m pytest -q` before you finish; the harness runs the full tier.

## Work order

1. Read this spec and both fixtures. They define the formats; nothing else does. Do not assume a
   field they do not contain.
2. Read `TASK_BACKLOG.md`. Implement every item marked `[scope]`. Implement no item marked `[later]`.
3. Read the three test files at the root. Do not modify them.
4. Implement `feeds/money.py`: `parse_money`, `round_half_away`, `format_money`.
5. Implement `feeds/pricelist.py`: `load_pricelist`, the six columns, the skipped-row list.
6. Implement `feeds/orders.py`: `load_orders`, the version check, unknown keys ignored.
7. Implement `rules/pricing.py`: whole-pack billing, the discount bands, the tax classes.
8. Implement `rules/validation.py`: the three rejection reasons, in the stated order.
9. Implement `rules/stock.py`: allocation order, whole-pack part service, backorders.
10. Implement `pipeline.py`: `process_orders` over the four rule modules.
11. Implement `cli.py`: `main(argv)`, two positional arguments, exit 2 on any other count.
12. Create no file that is not listed under Files: no module, no configuration, no documentation.
13. Run `python -m pytest -q`.
14. Report what was done, and which `TASK_BACKLOG.md` items were left alone.
