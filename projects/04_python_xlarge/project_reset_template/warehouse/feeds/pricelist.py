"""Reader for the semicolon price list; the fixture defines the format."""

from collections import namedtuple

COLUMNS = ("sku", "name", "unit_price", "currency", "pack_size", "tax_class")

PriceRow = namedtuple("PriceRow", "sku name unit_price currency pack_size tax_class")


def load_pricelist(path):
    """Read the price list; return ({sku: PriceRow}, skipped) with skipped the raw rows."""
    raise NotImplementedError
