"""Held-out suite -- never copied into the project_workspace (oam_targetpicture.md ch.11).

Same public contract as test_ledger.py, different inputs: both locale conventions inside one file,
a parenthesised zero, negative rounding at the half cent, rule precedence over overlapping
keywords, the month boundary, a malformed line between valid ones, and the CLI on empty input.
"""
from datetime import date

import pytest

from ledger.cli import main
from ledger.parse import Transaction, parse_amount, parse_lines
from ledger.report import aggregate, format_report, round_half_away
from ledger.rules import categorise

MIXED = """\
# both conventions, one file
2026-04-02;Rewe Grossmarkt;(2.000,00)

2026-04-03;Salary April;1,234.56
2026-04-04;Rent April;(1.500,00)
"""


# --- parse ----------------------------------------------------------------

def test_amount_repeated_group_separators_in_both_conventions():
    assert parse_amount("1.234.567,89") == 1234567.89
    assert parse_amount("1,234,567.89") == 1234567.89
    assert parse_amount("1.234.567") == 1234567.0
    assert parse_amount("1,234,567") == 1234567.0


def test_amount_negatives_and_the_parenthesised_zero():
    assert parse_amount("-1.234,50") == -1234.5
    assert parse_amount("(2,000.00)") == -2000.0
    assert parse_amount("(0,00)") == 0.0
    assert parse_amount("(0.00)") == 0.0


def test_amount_rejects_further_malformed_text():
    for bad in ("1,,00", "12.50-", "()"):
        with pytest.raises(ValueError):
            parse_amount(bad)


def test_lines_read_both_conventions_from_one_file():
    transactions, errors = parse_lines(MIXED.splitlines())
    assert errors == []
    assert [t.amount for t in transactions] == [-2000.0, 1234.56, -1500.0]
    assert transactions[0] == Transaction(date(2026, 4, 2), "Rewe Grossmarkt", -2000.0)


def test_lines_keep_the_order_around_a_malformed_line():
    transactions, errors = parse_lines(
        ["2026-05-01;first;1,00", "  2026-05-02;broken;12,50x  ", "2026-05-03;second;2,00",
         "2026-02-30;impossible date;3,00", "2026-05-04;third;3,00"])
    assert [t.description for t in transactions] == ["first", "second", "third"]
    assert errors == ["2026-05-02;broken;12,50x", "2026-02-30;impossible date;3,00"]


# --- rules ----------------------------------------------------------------

def test_rule_precedence_when_two_default_keywords_match():
    assert categorise("Netflix bundle billed with rent") == "housing"
    assert categorise("Salary and rent settlement") == "income"


def test_match_is_a_substring_anywhere_and_case_insensitive():
    assert categorise("xxREWExx") == "groceries"
    assert categorise("MONTHLY NETFLIX") == "subscriptions"
    assert categorise("Netflix", (("NETFLIX", "streaming"),)) == "streaming"


# --- report ---------------------------------------------------------------

def test_round_half_away_at_other_half_values():
    assert round_half_away(-1.005) == -1.01
    assert round_half_away(0.005) == 0.01
    assert round_half_away(-2.5, 0) == -3.0
    assert round_half_away(-2.4, 0) == -2.0


def test_aggregate_rounds_the_sum_not_the_transactions():
    transactions = [Transaction(date(2026, 6, 1), "Netflix", 0.004),
                    Transaction(date(2026, 6, 2), "Netflix", 0.004)]
    assert aggregate(transactions) == {("2026-06", "subscriptions"): 0.01}


def test_aggregate_splits_march_from_april():
    transactions, _ = parse_lines(MIXED.splitlines())
    transactions.append(Transaction(date(2026, 3, 31), "Rent March", -1500.0))
    assert aggregate(transactions) == {("2026-03", "housing"): -1500.0,
                                       ("2026-04", "groceries"): -2000.0,
                                       ("2026-04", "income"): 1234.56,
                                       ("2026-04", "housing"): -1500.0}
    assert format_report(aggregate(transactions)).splitlines()[0] == "2026-03;housing;-1500.00"


# --- cli ------------------------------------------------------------------

def test_cli_on_a_file_without_transactions(tmp_path, capsys):
    path = tmp_path / "empty.txt"
    path.write_text("# nothing here\n\n", encoding="utf-8")
    assert main([str(path)]) == 0
    assert "skipped" not in capsys.readouterr().out


def test_cli_counts_every_malformed_line(tmp_path, capsys):
    path = tmp_path / "broken.txt"
    path.write_text("rubbish\n2026-04-03;Salary April;1,234.56\nx;y;z;w\nalso rubbish\n",
                    encoding="utf-8")
    assert main([str(path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("2026-04;income;1234.56\n")
    assert out.rstrip().endswith("skipped 3 malformed line(s)")
