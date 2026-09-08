"""Held-out suite -- never copied into the project_workspace (oam_targetpicture.md ch.11).

The same pinned behaviour as test_pricing.py on inputs it does not cover: zero and negative
quantities, missing keys, rounding at the half cent, the free-shipping boundary from both sides,
and customer types outside the table.
"""
from pricing import discount_rate, shipping_cost, subtotal, total


def test_subtotal_ignores_negative_quantity_and_negative_price():
    assert subtotal([{"unit_price": 10.0, "quantity": -2}]) == 0.0
    assert subtotal([{"unit_price": -5.0, "quantity": 2}]) == 0.0
    assert subtotal([{"unit_price": -5.0, "quantity": 2}, {"unit_price": 3.0, "quantity": 2}]) == 6.0


def test_subtotal_ignores_a_line_with_neither_key():
    assert subtotal([{}]) == 0.0
    assert subtotal([{}, {"unit_price": 2.0, "quantity": 3}]) == 6.0


def test_subtotal_zero_quantity_among_valid_lines():
    assert subtotal([{"unit_price": 10.0, "quantity": 0}, {"unit_price": 3.0, "quantity": 2}]) == 6.0


def test_subtotal_rounds_half_to_even_at_the_cent():
    assert subtotal([{"unit_price": 0.125, "quantity": 1}]) == 0.12
    assert subtotal([{"unit_price": 2.675, "quantity": 1}]) == 2.67
    assert subtotal([{"unit_price": 0.135, "quantity": 1}]) == 0.14


def test_shipping_at_the_boundary_from_both_sides():
    assert shipping_cost(50.01, False) == 0.0
    assert shipping_cost(0.0, False) == 4.95
    assert shipping_cost(49.99, True) == 12.5


def test_discount_rate_is_case_sensitive_and_defaults_to_zero():
    assert discount_rate("") == 0.0
    assert discount_rate("MEMBER") == 0.0
    assert discount_rate(None) == 0.0


def test_total_discount_rounding_reaches_the_free_shipping_threshold():
    assert total([{"unit_price": 52.63, "quantity": 1}], "member") == 59.5


def test_total_on_customer_types_and_a_zero_quantity_line():
    assert total([{"unit_price": 19.99, "quantity": 3}], "staff") == 60.65
    assert total([{"unit_price": 19.99, "quantity": 3}], "gold") == 71.36
    assert total([{"unit_price": 19.99, "quantity": 3}], "member", express=True) == 82.67
    assert total([{"unit_price": 10.0, "quantity": 0},
                  {"unit_price": 25.0, "quantity": 4}]) == 119.0
