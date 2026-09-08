"""Reader for the semicolon price list; the fixture defines the format."""

import csv
from collections import namedtuple

from warehouse import FeedError
from warehouse.feeds.money import parse_money
from warehouse.rules.pricing import TAX_RATES

COLUMNS = ("sku", "name", "unit_price", "currency", "pack_size", "tax_class")

PriceRow = namedtuple("PriceRow", "sku name unit_price currency pack_size tax_class")


def _row(fields):
    """Build a PriceRow from six raw fields, or return None when the row is unusable."""
    sku, name, price, currency, pack, tax = [f.strip() for f in fields]
    if not sku or currency != "EUR" or tax not in TAX_RATES or not pack.isdigit() or pack == "0":
        return None
    try:
        return PriceRow(sku, name, parse_money(price), currency, int(pack), tax)
    except ValueError:
        return None


def load_pricelist(path):
    """Read the price list; return ({sku: PriceRow}, skipped) with skipped the raw rows."""
    with open(str(path), encoding="utf-8", newline="") as handle:
        rows = [r for r in csv.reader(handle, delimiter=";") if r]
    if not rows or tuple(f.strip() for f in rows[0]) != COLUMNS:
        raise FeedError("price list header is not %s" % (COLUMNS,))
    prices, skipped = {}, []
    for fields in rows[1:]:
        row = _row(fields) if len(fields) == len(COLUMNS) else None
        if row is None:
            skipped.append(fields)
        elif row.sku in prices:
            raise FeedError("duplicate sku: %s" % row.sku)
        else:
            prices[row.sku] = row
    return prices, skipped
