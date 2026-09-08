from datetime import date

import pytest

from ledger.cli import main
from ledger.parse import Transaction, parse_amount, parse_lines
from ledger.report import aggregate, format_report, round_half_away
from ledger.rules import categorise

SAMPLE = """\
# january
2026-01-15;REWE Markt;(32,68)

2026-01-31;Salary January;2.000,00
2026-02-01;Rent February;(800.00)
"""

REPORT = ("2026-01;groceries;-32.68\n"
          "2026-01;income;2000.00\n"
          "2026-02;housing;-800.00")


# --- parse ----------------------------------------------------------------

def test_amount_plain():
    assert parse_amount("12.50") == 12.5
    assert parse_amount("  7 ") == 7.0


def test_amount_german_format():
    assert parse_amount("1.234,56") == 1234.56


def test_amount_english_format():
    assert parse_amount("1,234.56") == 1234.56


def test_amount_group_separator_only():
    assert parse_amount("1.234") == 1234.0
    assert parse_amount("1,234") == 1234.0


def test_amount_parentheses_are_negative():
    assert parse_amount("(12.50)") == -12.5
    assert parse_amount("(1.234,56)") == -1234.56


def test_amount_leading_minus():
    assert parse_amount("-12,50") == -12.5


def test_amount_malformed_raises():
    for bad in ("", "   ", "abc", "12,50x", "(12.50"):
        with pytest.raises(ValueError):
            parse_amount(bad)


def test_lines_parse_the_three_fields():
    transactions, errors = parse_lines(["2026-01-15; REWE Markt ;(32,68)"])
    assert transactions == [Transaction(date(2026, 1, 15), "REWE Markt", -32.68)]
    assert errors == []


def test_lines_skip_blank_and_comment_lines():
    transactions, errors = parse_lines(SAMPLE.splitlines())
    assert errors == []
    assert [t.description for t in transactions] == [
        "REWE Markt", "Salary January", "Rent February"]


def test_lines_collect_the_malformed_lines():
    transactions, errors = parse_lines(
        ["2026-01-15;a;1,00", "rubbish", "2026-13-01;b;2,00", "2026-01-16;c;nope", "x;y;z;w"])
    assert [t.amount for t in transactions] == [1.0]
    assert errors == ["rubbish", "2026-13-01;b;2,00", "2026-01-16;c;nope", "x;y;z;w"]


def test_lines_empty_input():
    assert parse_lines([]) == ([], [])


# --- rules ----------------------------------------------------------------

def test_rule_order_is_the_precedence():
    rules = (("super", "A"), ("market", "B"))
    assert categorise("Supermarket Berlin", rules) == "A"
    assert categorise("Supermarket Berlin", tuple(reversed(rules))) == "B"


def test_match_is_a_case_insensitive_substring():
    assert categorise("REWE Markt") == "groceries"
    assert categorise("monthly rent, flat 3") == "housing"


def test_fallback_when_no_rule_matches():
    assert categorise("Cash withdrawal") == "other"
    assert categorise("Cash withdrawal", (("x", "y"),), "unknown") == "unknown"


# --- report ---------------------------------------------------------------

def test_round_half_away_from_zero_positive():
    assert round_half_away(2.675) == 2.68
    assert round_half_away(0.125) == 0.13
    assert round_half_away(1.005) == 1.01


def test_round_half_away_from_zero_negative():
    assert round_half_away(-2.675) == -2.68
    assert round_half_away(-0.125) == -0.13


def test_round_half_away_leaves_other_values_alone():
    assert round_half_away(2.674) == 2.67
    assert round_half_away(3.0) == 3.0
    assert round_half_away(1.5, 0) == 2.0


def test_aggregate_by_month_and_category():
    transactions, _ = parse_lines(SAMPLE.splitlines())
    assert aggregate(transactions) == {("2026-01", "groceries"): -32.68,
                                       ("2026-01", "income"): 2000.0,
                                       ("2026-02", "housing"): -800.0}


def test_aggregate_splits_at_the_month_boundary():
    transactions = [Transaction(date(2026, 1, 31), "Netflix", -9.99),
                    Transaction(date(2026, 2, 1), "Netflix", -9.99)]
    assert aggregate(transactions) == {("2026-01", "subscriptions"): -9.99,
                                       ("2026-02", "subscriptions"): -9.99}


def test_aggregate_rounds_the_category_total_half_away_from_zero():
    transactions = [Transaction(date(2026, 3, 1), "Netflix", 0.125),
                    Transaction(date(2026, 3, 2), "Netflix", 0.0)]
    assert aggregate(transactions) == {("2026-03", "subscriptions"): 0.13}


def test_format_report_lines():
    transactions, _ = parse_lines(SAMPLE.splitlines())
    assert format_report(aggregate(transactions)) == REPORT


def test_format_report_empty():
    assert format_report({}) == ""


# --- cli ------------------------------------------------------------------

def test_cli_prints_the_report(tmp_path, capsys):
    path = tmp_path / "ledger.txt"
    path.write_text(SAMPLE, encoding="utf-8")
    assert main([str(path)]) == 0
    assert capsys.readouterr().out == REPORT + "\n"


def test_cli_reports_skipped_lines(tmp_path, capsys):
    path = tmp_path / "ledger.txt"
    path.write_text(SAMPLE + "rubbish\nmore rubbish\n", encoding="utf-8")
    assert main([str(path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith(REPORT + "\n")
    assert out.rstrip().endswith("skipped 2 malformed line(s)")
