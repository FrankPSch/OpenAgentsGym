"""Held-out suite -- never copied into the project_workspace (oam_targetpicture.md ch.11).

The pipeline on inputs the visible suite does not use: two orders placed on the same day, a sku
short in more than one order, a feed with no orders at all, and a feed in which some orders are
rejected while the rest are still processed.
"""
import json
from pathlib import Path

import warehouse
from warehouse.feeds.orders import Order, OrderLine, load_orders
from warehouse.feeds.pricelist import PriceRow, load_pricelist
from warehouse.pipeline import process_orders

FIXTURES = Path(warehouse.__file__).resolve().parent.parent / "fixtures"
PART = PriceRow("P-1", "Teil", 100, "EUR", 2, "standard")
PRICES = {PART.sku: PART}


def order(order_id, placed, qty):
    return Order(order_id, "Kunde", placed, [OrderLine(PART.sku, qty)])


def write_json(tmp_path, feed):
    path = tmp_path / "orders.json"
    path.write_text(json.dumps(feed), encoding="utf-8")
    return path


def test_two_orders_placed_on_the_same_day_are_taken_by_order_id():
    result = process_orders(PRICES, [order("D-2", "2026-05-01", 4),
                                     order("D-1", "2026-05-01", 4)], {"P-1": 4})
    assert list(result.totals) == ["D-1", "D-2"]
    assert result.backorders == {"P-1": 4}


def test_a_sku_short_in_two_orders_aggregates_into_one_backorder():
    result = process_orders(PRICES, [order("D-1", "2026-05-01", 4),
                                     order("D-2", "2026-05-02", 4)], {"P-1": 2})
    assert result.backorders == {"P-1": 6}
    assert result.totals["D-1"]["net"] == 400


def test_a_feed_without_orders_produces_an_empty_result(tmp_path):
    path = write_json(tmp_path, {"feed_version": 2, "generated": "2026-05-01", "orders": []})
    prices, _ = load_pricelist(FIXTURES / "pricelist.csv")
    result = process_orders(prices, load_orders(path), {})
    assert load_orders(path) == []
    assert (result.lines, result.totals, result.backorders, result.rejects) == ([], {}, {}, [])


def test_a_rejected_order_does_not_stop_the_rest_of_the_feed(tmp_path):
    path = write_json(tmp_path, {"feed_version": 2, "orders": [
        {"order_id": "E-1", "customer": "K", "placed": "01/05/2026",
         "lines": [{"sku": "SKU-1001", "qty": 5}]},
        {"order_id": "E-2", "customer": "K", "placed": "2026-05-02",
         "lines": [{"sku": "SKU-1001", "qty": 5}]},
        {"order_id": "E-3", "customer": "K", "placed": "2026-05-03",
         "lines": [{"sku": "SKU-1001", "qty": -2}]}]})
    prices, _ = load_pricelist(FIXTURES / "pricelist.csv")
    result = process_orders(prices, load_orders(path), {})
    assert [reject[0] for reject in result.rejects] == ["E-1", "E-3"]
    assert result.rejects[0][1] == ["unparsable date: 01/05/2026"]
    assert list(result.totals) == ["E-2"]
    assert result.totals["E-2"]["net"] == 2450
