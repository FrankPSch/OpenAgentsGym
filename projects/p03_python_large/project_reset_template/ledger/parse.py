"""Parsing of ledger lines: YYYY-MM-DD;description;amount."""

from collections import namedtuple

Transaction = namedtuple("Transaction", "date description amount")


def parse_amount(text):
    """Parse an amount written in the de or en convention; return a float.

    Raises ValueError when the text is not an amount.
    """
    raise NotImplementedError


def parse_lines(lines):
    """Parse an iterable of ledger lines; return (transactions, errors).

    errors is a list of the malformed lines, stripped, in the order they appeared.
    """
    raise NotImplementedError
