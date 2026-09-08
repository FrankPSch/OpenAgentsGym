"""Held-out suite -- never copied into the project_workspace (oam_targetpicture.md ch.11).

Format fidelity: the two fixtures are the whole definition of the two formats, so a column or a
key that is not in them must not be invented, and one that is must be read exactly as it stands.
"""
import json
from pathlib import Path

import pytest

import warehouse
from warehouse import FeedError
from warehouse.feeds.money import parse_money
from warehouse.feeds.orders import Order, OrderLine, load_orders
from warehouse.feeds.pricelist import load_pricelist
from warehouse.pipeline import process_orders

FIXTURES = Path(warehouse.__file__).resolve().parent.parent / "fixtures"
HEADER = "sku;name;unit_price;currency;pack_size;tax_class"


def write_csv(tmp_path, text):
    path = tmp_path / "prices.csv"
    path.write_text(text, encoding="utf-8")
    return path


def write_json(tmp_path, feed):
    path = tmp_path / "orders.json"
    path.write_text(json.dumps(feed), encoding="utf-8")
    return path


def test_a_seventh_column_in_the_header_is_a_feed_error(tmp_path):
    path = write_csv(tmp_path, HEADER + ";discount\nSKU-A;Ordner;3,90;EUR;5;standard;10\n")
    with pytest.raises(FeedError):
        load_pricelist(path)


def test_a_blank_line_is_ignored_and_is_not_a_skipped_row(tmp_path):
    path = write_csv(tmp_path, HEADER + "\n\nSKU-A;Ordner;3,90;EUR;5;standard\n\n"
                                        "SKU-B;Stift;1,10;EUR;2;reduced\n")
    prices, skipped = load_pricelist(path)
    assert sorted(prices) == ["SKU-A", "SKU-B"]
    assert skipped == []


def test_a_duplicate_sku_is_a_feed_error_even_with_the_same_price(tmp_path):
    path = write_csv(tmp_path, HEADER + "\nSKU-A;Ordner;3,90;EUR;5;standard\n"
                                        "SKU-B;Stift;1,10;EUR;2;reduced\n"
                                        "SKU-A;Ordner;3,90;EUR;5;standard\n")
    with pytest.raises(FeedError):
        load_pricelist(path)


def test_the_comma_decimal_of_the_price_list_becomes_cents():
    prices, _ = load_pricelist(FIXTURES / "pricelist.csv")
    assert prices["SKU-1002"].unit_price == 89
    assert prices["SKU-4002"].unit_price == 2499
    assert parse_money("0,89") == 89 and parse_money("199,00") == 19900


def test_an_unknown_json_key_is_ignored_at_every_level(tmp_path):
    path = write_json(tmp_path, {"feed_version": 2, "generated": "2026-04-01", "source": "erp",
                                 "orders": [{"order_id": "C-1", "customer": "K", "priority": "high",
                                             "placed": "2026-04-01", "total": 999,
                                             "lines": [{"sku": "SKU-1001", "qty": 3,
                                                        "price": 100, "currency": "USD"}]}]})
    order = load_orders(path)[0]
    assert order == Order("C-1", "K", "2026-04-01", [OrderLine("SKU-1001", 3)])
    assert Order._fields == ("order_id", "customer", "placed", "lines")
    assert OrderLine._fields == ("sku", "qty")


def test_a_missing_customer_defaults_and_missing_lines_is_empty(tmp_path):
    path = write_json(tmp_path, {"feed_version": 2, "orders": [
        {"order_id": "C-2", "placed": "2026-04-02"}]})
    assert load_orders(path) == [Order("C-2", "", "2026-04-02", [])]


def test_a_feed_version_other_than_two_is_rejected(tmp_path):
    for version in (1, 3, None):
        path = write_json(tmp_path, {"feed_version": version, "orders": []})
        with pytest.raises(FeedError):
            load_orders(path)


def test_a_sku_absent_from_the_price_list_is_a_reject_and_not_a_zero_price(tmp_path):
    prices, _ = load_pricelist(FIXTURES / "pricelist.csv")
    path = write_json(tmp_path, {"feed_version": 2, "orders": [
        {"order_id": "C-3", "customer": "K", "placed": "2026-04-03",
         "lines": [{"sku": "SKU-5001", "qty": 5}]}]})
    result = process_orders(prices, load_orders(path), {})
    assert result.rejects == [("C-3", ["unknown sku: SKU-5001"])]
    assert result.totals == {} and result.lines == []
