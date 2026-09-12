"""Visible suite: pricing, stock allocation and order validation (18 tests)."""
from warehouse.feeds.orders import Order, OrderLine
from warehouse.feeds.pricelist import PriceRow
from warehouse.rules.pricing import discount_band, line_total, tax_for
from warehouse.rules.stock import allocate
from warehouse.rules.validation import validate_order

PAPER = PriceRow("SKU-1001", "Kopierpapier A4", 490, "EUR", 5, "standard")
COFFEE = PriceRow("SKU-2001", "Kaffeebohnen 1kg", 1295, "EUR", 6, "reduced")
BOOK = PriceRow("SKU-3001", "Lehrbuch Logistik", 3900, "EUR", 1, "zero")
PRICES = {row.sku: row for row in (PAPER, COFFEE, BOOK)}


def order(order_id, placed, *lines):
    return Order(order_id, "Kunde", placed, [OrderLine(sku, qty) for sku, qty in lines])


# --- pricing --------------------------------------------------------------

def test_line_total_bills_whole_packs():
    assert line_total(PAPER, 12) == 15 * 490


def test_line_total_of_a_single_started_pack():
    assert line_total(COFFEE, 1) == 6 * 1295


def test_line_total_of_a_pack_size_of_one():
    assert line_total(BOOK, 2) == 7800


def test_discount_band_below_the_first_threshold():
    assert discount_band(9999) == 0


def test_discount_band_of_three_percent():
    assert discount_band(17790) == 3


def test_discount_band_of_five_percent():
    assert discount_band(67056) == 5


def test_discount_band_of_eight_percent():
    assert discount_band(250000) == 8


def test_tax_for_the_three_classes():
    assert tax_for(PAPER, 10000) == 1900
    assert tax_for(COFFEE, 10000) == 700
    assert tax_for(BOOK, 10000) == 0


# --- stock ----------------------------------------------------------------

def test_allocate_serves_everything_when_the_sku_is_not_in_stock_mapping():
    served, backorders = allocate([order("B-1", "2026-01-02", ("SKU-1001", 12))], {}, PRICES)
    assert served == {"B-1": {"SKU-1001": 15}}
    assert backorders == {}


def test_allocate_serves_whole_packs_only():
    served, backorders = allocate([order("B-1", "2026-01-02", ("SKU-1001", 12))],
                                  {"SKU-1001": 12}, PRICES)
    assert served == {"B-1": {"SKU-1001": 10}}
    assert backorders == {"SKU-1001": 5}


def test_allocate_backorders_a_sku_that_is_out_of_stock():
    served, backorders = allocate([order("B-1", "2026-01-02", ("SKU-3001", 4))],
                                  {"SKU-3001": 0}, PRICES)
    assert served == {"B-1": {}}
    assert backorders == {"SKU-3001": 4}


def test_allocate_takes_the_older_order_first():
    orders = [order("B-2", "2026-01-05", ("SKU-3001", 3)),
              order("B-1", "2026-01-02", ("SKU-3001", 3))]
    served, backorders = allocate(orders, {"SKU-3001": 3}, PRICES)
    assert served == {"B-1": {"SKU-3001": 3}, "B-2": {}}
    assert backorders == {"SKU-3001": 3}


def test_allocate_does_not_modify_the_stock_mapping():
    stock = {"SKU-3001": 5}
    allocate([order("B-1", "2026-01-02", ("SKU-3001", 2))], stock, PRICES)
    assert stock == {"SKU-3001": 5}


def test_allocate_ignores_a_line_whose_sku_is_unknown():
    served, backorders = allocate([order("B-1", "2026-01-02", ("SKU-9999", 4))], {}, PRICES)
    assert served == {"B-1": {}}
    assert backorders == {}


# --- validation -----------------------------------------------------------

def test_validate_accepts_a_good_order():
    assert validate_order(order("B-1", "2026-01-02", ("SKU-1001", 4)), PRICES) == []


def test_validate_reports_an_unknown_sku():
    assert validate_order(order("B-1", "2026-01-02", ("SKU-9999", 4)), PRICES) == [
        "unknown sku: SKU-9999"]


def test_validate_reports_a_non_positive_qty():
    assert validate_order(order("B-1", "2026-01-02", ("SKU-1001", 0)), PRICES) == [
        "non-positive qty: SKU-1001"]


def test_validate_reports_an_unparsable_date_before_the_line_reasons():
    assert validate_order(order("B-1", "02.01.2026", ("SKU-9999", 4)), PRICES) == [
        "unparsable date: 02.01.2026", "unknown sku: SKU-9999"]
