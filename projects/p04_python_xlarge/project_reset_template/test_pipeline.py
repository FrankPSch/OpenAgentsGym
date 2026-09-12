"""Visible suite: the pipeline over the fixtures, and the command line (14 tests)."""
from pathlib import Path

from warehouse.cli import main
from warehouse.feeds.orders import Order, OrderLine, load_orders
from warehouse.feeds.pricelist import load_pricelist
from warehouse.pipeline import process_orders

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def feeds():
    prices, _ = load_pricelist(FIXTURES / "pricelist.csv")
    return prices, load_orders(FIXTURES / "orders.json")


# --- pipeline -------------------------------------------------------------

def test_pipeline_processes_the_accepted_orders_in_allocation_order():
    prices, orders = feeds()
    assert list(process_orders(prices, orders, {}).totals) == ["A-1003", "A-1001", "A-1002",
                                                               "A-1004"]


def test_pipeline_totals_of_one_order():
    prices, orders = feeds()
    assert process_orders(prices, orders, {}).totals["A-1001"] == {
        "net": 17790, "discount": 534, "handling": 0, "tax": 2375, "gross": 19631}


def test_pipeline_discount_is_the_sum_of_the_line_cuts():
    prices, orders = feeds()
    totals = process_orders(prices, orders, {}).totals["A-1003"]
    assert totals["net"] == 67056
    assert totals["discount"] == 3353
    assert totals["gross"] == 74397


def test_pipeline_lines_carry_the_billed_units_and_the_line_net():
    prices, orders = feeds()
    lines = process_orders(prices, orders, {}).lines
    assert len(lines) == 12
    assert lines[0] == ("A-1003", "SKU-4001", 3, 44700)
    assert ("A-1001", "SKU-1001", 15, 7350) in lines


def test_pipeline_collects_the_rejects_in_feed_order():
    prices, orders = feeds()
    assert process_orders(prices, orders, {}).rejects == [
        ("A-1005", ["unknown sku: SKU-9999"]), ("A-1006", ["non-positive qty: SKU-1001"])]


def test_pipeline_does_not_price_a_rejected_order():
    prices, orders = feeds()
    result = process_orders(prices, orders, {})
    assert "A-1005" not in result.totals
    assert [line for line in result.lines if line[0] == "A-1006"] == []


def test_pipeline_taxes_the_zero_class_at_nothing():
    prices, orders = feeds()
    assert process_orders(prices, orders, {}).totals["A-1002"]["tax"] == 0


def test_pipeline_adds_the_handling_fee_to_a_small_order():
    prices, _ = feeds()
    small = Order("B-1", "Kleinkunde", "2026-03-04", [OrderLine("SKU-1002", 5)])
    assert process_orders(prices, [small], {}).totals["B-1"] == {
        "net": 890, "discount": 0, "handling": 490, "tax": 169, "gross": 1549}


def test_pipeline_reports_the_backorders_of_a_limited_stock():
    prices, orders = feeds()
    assert process_orders(prices, orders, {"SKU-4001": 2}).backorders == {"SKU-4001": 1}


# --- cli ------------------------------------------------------------------

def test_cli_prints_one_order_line_per_accepted_order(capsys):
    assert main([str(FIXTURES / "pricelist.csv"), str(FIXTURES / "orders.json")]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "ORDER;A-1003;743.97"
    assert lines[:4] == ["ORDER;A-1003;743.97", "ORDER;A-1001;196.31", "ORDER;A-1002;125.13",
                         "ORDER;A-1004;141.24"]


def test_cli_prints_one_reject_line_per_reason(capsys):
    assert main([str(FIXTURES / "pricelist.csv"), str(FIXTURES / "orders.json")]) == 0
    out = capsys.readouterr().out
    assert "REJECT;A-1005;unknown sku: SKU-9999" in out
    assert "REJECT;A-1006;non-positive qty: SKU-1001" in out


def test_cli_prints_no_backorder_line_when_stock_is_unknown(capsys):
    assert main([str(FIXTURES / "pricelist.csv"), str(FIXTURES / "orders.json")]) == 0
    assert "BACKORDER" not in capsys.readouterr().out


def test_cli_returns_two_without_arguments(capsys):
    assert main([]) == 2
    assert capsys.readouterr().out == ""


def test_cli_returns_two_on_one_argument(capsys):
    assert main([str(FIXTURES / "pricelist.csv")]) == 2
    assert capsys.readouterr().out == ""
