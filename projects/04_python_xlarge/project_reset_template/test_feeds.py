"""Visible suite: the two feed readers and the money helpers (18 tests)."""
import json
from pathlib import Path

import pytest

from warehouse import FeedError
from warehouse.feeds.money import format_money, parse_money, round_half_away
from warehouse.feeds.orders import Order, OrderLine, load_orders
from warehouse.feeds.pricelist import PriceRow, load_pricelist

FIXTURES = Path(__file__).resolve().parent / "fixtures"
HEADER = "sku;name;unit_price;currency;pack_size;tax_class"


def write_csv(tmp_path, *rows):
    path = tmp_path / "prices.csv"
    path.write_text("\n".join((HEADER,) + rows) + "\n", encoding="utf-8")
    return path


def write_json(tmp_path, feed):
    path = tmp_path / "orders.json"
    path.write_text(json.dumps(feed), encoding="utf-8")
    return path


# --- money ----------------------------------------------------------------

def test_parse_money_reads_the_comma_decimal():
    assert parse_money("12,50") == 1250
    assert parse_money("12,5") == 1250
    assert parse_money("7") == 700
    assert parse_money("  4,90 ") == 490
    assert parse_money("-3,05") == -305


def test_parse_money_rejects_what_is_not_an_amount():
    for bad in ("", "   ", "abc", "12.50", "1.234,56", "12,505", "+5", "12,50-"):
        with pytest.raises(ValueError):
            parse_money(bad)


def test_round_half_away_and_format_money():
    assert round_half_away(2.5) == 3
    assert round_half_away(-2.5) == -3
    assert round_half_away(2.4) == 2
    assert format_money(123456) == "1234.56"
    assert format_money(-1250) == "-12.50"
    assert format_money(0) == "0.00"


# --- price list -----------------------------------------------------------

def test_pricelist_loads_the_usable_rows():
    prices, _ = load_pricelist(FIXTURES / "pricelist.csv")
    assert sorted(prices) == ["SKU-1001", "SKU-1002", "SKU-1003", "SKU-2001", "SKU-2002",
                              "SKU-2003", "SKU-3001", "SKU-3002", "SKU-4001", "SKU-4002"]


def test_pricelist_row_carries_the_six_columns():
    prices, _ = load_pricelist(FIXTURES / "pricelist.csv")
    assert prices["SKU-1001"] == PriceRow("SKU-1001", "Kopierpapier A4", 490, "EUR", 5, "standard")
    assert prices["SKU-2001"].tax_class == "reduced"
    assert prices["SKU-3001"].pack_size == 1


def test_pricelist_collects_the_skipped_rows():
    prices, skipped = load_pricelist(FIXTURES / "pricelist.csv")
    assert [row[0] for row in skipped] == ["SKU-5001", "SKU-5002", "SKU-5003", "SKU-6001"]
    assert not any(sku.startswith(("SKU-5", "SKU-6")) for sku in prices)


def test_pricelist_skips_a_price_that_is_not_an_amount(tmp_path):
    path = write_csv(tmp_path, "SKU-A;Ordner;3.90;EUR;5;standard", "SKU-B;Stift;1,10;EUR;2;standard")
    prices, skipped = load_pricelist(path)
    assert list(prices) == ["SKU-B"]
    assert [row[0] for row in skipped] == ["SKU-A"]


def test_pricelist_skips_a_pack_size_that_is_not_positive(tmp_path):
    path = write_csv(tmp_path, "SKU-A;Locher;6,40;EUR;zwei;standard",
                     "SKU-B;Locher;6,40;EUR;0;standard", "SKU-C;Locher;6,40;EUR;3;standard")
    prices, skipped = load_pricelist(path)
    assert list(prices) == ["SKU-C"]
    assert len(skipped) == 2


def test_pricelist_skips_an_unknown_tax_class_and_a_foreign_currency(tmp_path):
    path = write_csv(tmp_path, "SKU-A;Toner;89,00;EUR;1;luxury", "SKU-B;Stapler;199,00;USD;1;standard")
    prices, skipped = load_pricelist(path)
    assert prices == {}
    assert len(skipped) == 2


def test_pricelist_rejects_a_header_that_is_not_the_six_columns(tmp_path):
    path = tmp_path / "wrong.csv"
    path.write_text("sku;name;price;currency;pack_size;tax_class\n", encoding="utf-8")
    with pytest.raises(FeedError):
        load_pricelist(path)


def test_pricelist_rejects_a_duplicate_sku(tmp_path):
    path = write_csv(tmp_path, "SKU-A;Ordner;3,90;EUR;5;standard", "SKU-A;Ordner;4,10;EUR;5;standard")
    with pytest.raises(FeedError):
        load_pricelist(path)


# --- order feed -----------------------------------------------------------

def test_orders_loads_every_order_in_feed_order():
    orders = load_orders(FIXTURES / "orders.json")
    assert [o.order_id for o in orders] == ["A-1001", "A-1002", "A-1003", "A-1004", "A-1005",
                                            "A-1006"]


def test_orders_reads_the_customer_and_the_placed_date():
    orders = load_orders(FIXTURES / "orders.json")
    assert orders[0].customer == "Nordwind GmbH"
    assert orders[0].placed == "2026-03-01"
    assert orders[2].placed == "2026-02-27"


def test_orders_reads_the_lines():
    orders = load_orders(FIXTURES / "orders.json")
    assert orders[0].lines == [OrderLine("SKU-1001", 12), OrderLine("SKU-1002", 30),
                               OrderLine("SKU-2001", 6)]
    assert sum(len(o.lines) for o in orders) == 17


def test_orders_ignores_a_key_the_format_does_not_define():
    orders = load_orders(FIXTURES / "orders.json")
    fourth = [o for o in orders if o.order_id == "A-1004"][0]
    assert Order._fields == ("order_id", "customer", "placed", "lines")
    assert len(fourth.lines) == 3


def test_orders_defaults_a_missing_customer(tmp_path):
    path = write_json(tmp_path, {"feed_version": 2, "orders": [
        {"order_id": "B-1", "placed": "2026-01-02", "lines": [{"sku": "SKU-1001", "qty": 1}]}]})
    assert load_orders(path)[0].customer == ""


def test_orders_rejects_another_feed_version(tmp_path):
    path = write_json(tmp_path, {"feed_version": 3, "orders": []})
    with pytest.raises(FeedError):
        load_orders(path)


def test_orders_rejects_a_line_without_an_integer_qty(tmp_path):
    path = write_json(tmp_path, {"feed_version": 2, "orders": [
        {"order_id": "B-1", "customer": "x", "placed": "2026-01-02",
         "lines": [{"sku": "SKU-1001", "qty": "three"}]}]})
    with pytest.raises(FeedError):
        load_orders(path)
