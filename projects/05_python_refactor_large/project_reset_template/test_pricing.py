"""Golden tests. These pin the current behaviour exactly and must not be modified."""
import pytest

from pricing import discount_rate, shipping_cost, subtotal, total

ITEMS = [{"unit_price": 10.0, "quantity": 3}, {"unit_price": 2.5, "quantity": 2}]


def test_subtotal():
    assert subtotal(ITEMS) == 35.0


def test_subtotal_ignores_bad_lines():
    assert subtotal([{"unit_price": 10.0, "quantity": 0},
                     {"unit_price": 0.0, "quantity": 5},
                     {"quantity": 2},
                     {"unit_price": 4.0}]) == 0.0


def test_subtotal_none_quantity():
    assert subtotal([{"unit_price": 10.0, "quantity": None}]) == 0.0


def test_subtotal_empty():
    assert subtotal([]) == 0.0


@pytest.mark.parametrize("kind,rate", [("none", 0.0), ("member", 0.05),
                                       ("staff", 0.15), ("unknown", 0.0)])
def test_discount_rate(kind, rate):
    assert discount_rate(kind) == rate


def test_shipping_standard_below_threshold():
    assert shipping_cost(49.99, False) == 4.95


def test_shipping_free_at_threshold():
    assert shipping_cost(50.0, False) == 0.0


def test_shipping_express_always_charged():
    assert shipping_cost(500.0, True) == 12.5


def test_total_plain():
    assert total(ITEMS) == 47.54


def test_total_member():
    assert total(ITEMS, "member") == 45.46


def test_total_staff_express():
    assert total(ITEMS, "staff", express=True) == 50.28


def test_total_free_shipping():
    assert total([{"unit_price": 25.0, "quantity": 4}], "none") == 119.0


def test_total_empty_order():
    assert total([]) == 5.89
