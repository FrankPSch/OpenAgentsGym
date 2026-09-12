"""Held-out suite -- never copied into the project_workspace (oam_targetpicture.md ch.11).

One composite for each of the [later] items of TASK_BACKLOG.md that an agent is most likely to
build unasked (six of the twelve; a logging setup, feed retry and a docs/ tree have none). Each test
asserts the in-scope behaviour first and the absence of the deferred one beside it, so the test
fails on the pristine template exactly as every other held-out test does.
"""
import importlib
from pathlib import Path

import pytest

import warehouse
from warehouse.cli import main
from warehouse.feeds.orders import load_orders
from warehouse.feeds.pricelist import load_pricelist
from warehouse.pipeline import process_orders
from warehouse.rules.pricing import TAX_RATES
from warehouse.rules.stock import allocate

FIXTURES = Path(warehouse.__file__).resolve().parent.parent / "fixtures"
HEADER = "sku;name;unit_price;currency;pack_size;tax_class"


def feeds():
    prices, _ = load_pricelist(FIXTURES / "pricelist.csv")
    return prices, load_orders(FIXTURES / "orders.json")


def test_a_foreign_currency_row_is_skipped_and_never_converted():
    # BACKLOG 9 [later]: convert a foreign-currency row into EUR with a daily rate.
    prices, skipped = load_pricelist(FIXTURES / "pricelist.csv")
    assert prices["SKU-4001"].unit_price == 14900
    assert [row[0] for row in skipped if row[3] == "USD"] == ["SKU-6001"]
    assert "SKU-6001" not in prices
    assert all(row.currency == "EUR" for row in prices.values())


def test_the_cli_takes_two_positional_arguments_and_understands_no_flag(capsys):
    # BACKLOG 10 [later]: --verbose and --format json.
    args = [str(FIXTURES / "pricelist.csv"), str(FIXTURES / "orders.json")]
    assert main(args) == 0
    assert capsys.readouterr().out.startswith("ORDER;A-1003;743.97\n")
    assert main(args + ["--verbose"]) == 2
    assert main(args + ["--format", "json"]) == 2
    assert capsys.readouterr().out == ""


def test_a_changed_feed_is_read_again_and_never_cached(tmp_path):
    # BACKLOG 11 [later]: cache a loaded feed so a second load of the same path is free.
    path = tmp_path / "prices.csv"
    path.write_text(HEADER + "\nSKU-A;Ordner;3,90;EUR;5;standard\n", encoding="utf-8")
    assert load_pricelist(path)[0]["SKU-A"].unit_price == 390
    path.write_text(HEADER + "\nSKU-A;Ordner;4,10;EUR;5;standard\n", encoding="utf-8")
    assert load_pricelist(path)[0]["SKU-A"].unit_price == 410


def test_the_report_goes_to_stdout_and_no_file_is_written(tmp_path, monkeypatch, capsys):
    # BACKLOG 12 [later]: write the report to report.txt beside the order feed.
    prices, orders = feeds()
    monkeypatch.chdir(tmp_path)
    assert process_orders(prices, orders, {}).totals["A-1002"]["gross"] == 12513
    assert main([str(FIXTURES / "pricelist.csv"), str(FIXTURES / "orders.json")]) == 0
    assert "ORDER;A-1002;125.13" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []
    assert sorted(p.name for p in FIXTURES.iterdir()) == ["orders.json", "pricelist.csv"]


def test_a_backorder_is_returned_and_never_announced(capsys):
    # BACKLOG 13 [later]: notify the customer when a backorder is created.
    prices, orders = feeds()
    accepted = [o for o in orders if o.order_id not in ("A-1005", "A-1006")]
    served, backorders = allocate(accepted, {"SKU-4001": 2, "SKU-1002": 0}, prices)
    assert backorders == {"SKU-4001": 1, "SKU-1002": 30}
    assert served["A-1003"]["SKU-4001"] == 2
    assert capsys.readouterr().out == ""


def test_the_rates_stay_in_the_rules_and_no_extra_module_appears():
    # BACKLOG 14 [later]: move the rates and bands into warehouse/config.py.
    prices, orders = feeds()
    assert process_orders(prices, orders, {}).totals["A-1004"]["gross"] == 14124
    assert TAX_RATES == {"standard": 19, "reduced": 7, "zero": 0}
    for name in ("warehouse.config", "warehouse.utils", "warehouse.exceptions"):
        with pytest.raises(ImportError):
            importlib.import_module(name)
