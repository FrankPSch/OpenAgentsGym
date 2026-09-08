"""Held-out suite -- never copied into the project_workspace (oam_targetpicture.md ch.11).

The rules at their boundaries: each discount threshold exactly, the handling fee exactly at
20.00, the half cent, the zero tax class and a quantity that is already a whole number of packs.
"""
from warehouse.feeds.money import round_half_away
from warehouse.feeds.orders import Order, OrderLine
from warehouse.feeds.pricelist import PriceRow
from warehouse.pipeline import process_orders
from warehouse.rules.pricing import discount_band, line_total, tax_for

PAPER = PriceRow("SKU-1001", "Kopierpapier A4", 490, "EUR", 5, "standard")
BOOK = PriceRow("SKU-3001", "Lehrbuch Logistik", 3900, "EUR", 1, "zero")


def one_line_order(row, qty):
    """A single-line order for `row`, priced through the whole pipeline."""
    order = Order("H-1", "Kunde", "2026-07-01", [OrderLine(row.sku, qty)])
    return process_orders({row.sku: row}, [order], {}).totals["H-1"]


def test_the_three_percent_band_starts_exactly_at_one_hundred():
    assert discount_band(9999) == 0
    assert discount_band(10000) == 3
    assert discount_band(10001) == 3


def test_the_five_percent_band_starts_exactly_at_five_hundred():
    assert discount_band(49999) == 3
    assert discount_band(50000) == 5


def test_the_eight_percent_band_starts_exactly_at_two_thousand():
    assert discount_band(199999) == 5
    assert discount_band(200000) == 8


def test_the_handling_fee_stops_exactly_at_twenty():
    row = PriceRow("H-A", "Handling", 1000, "EUR", 1, "standard")
    assert one_line_order(row, 2) == {"net": 2000, "discount": 0, "handling": 0,
                                      "tax": 380, "gross": 2380}
    cheap = PriceRow("H-B", "Handling", 1999, "EUR", 1, "standard")
    assert one_line_order(cheap, 1) == {"net": 1999, "discount": 0, "handling": 490,
                                        "tax": 380, "gross": 2869}


def test_the_half_cent_rounds_away_from_zero():
    assert round_half_away(0.5) == 1
    assert round_half_away(-0.5) == -1
    assert round_half_away(1.5) == 2
    assert round_half_away(1250, 100) == 1300
    assert round_half_away(-1250, 100) == -1300
    assert round_half_away(1249, 100) == 1200


def test_the_zero_tax_class_is_taxed_at_nothing():
    assert tax_for(BOOK, 123456) == 0
    assert one_line_order(BOOK, 3)["tax"] == 0


def test_a_quantity_that_is_already_whole_packs_bills_no_extra_pack():
    assert line_total(PAPER, 10) == 10 * 490
    assert line_total(PAPER, 5) == 5 * 490
    assert line_total(PAPER, 11) == 15 * 490
