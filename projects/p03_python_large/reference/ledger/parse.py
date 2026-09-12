"""Parsing of ledger lines: YYYY-MM-DD;description;amount."""

import re
from collections import namedtuple
from datetime import datetime

Transaction = namedtuple("Transaction", "date description amount")

DIGITS = re.compile(r"^\d+(?:[.,]\d+)*$")


def parse_amount(text):
    """Parse an amount written in the de or en convention; return a float.

    Raises ValueError when the text is not an amount.
    """
    body, negative = text.strip(), False
    if body.startswith("-"):
        body, negative = body[1:].strip(), True
    elif body.startswith("(") and body.endswith(")"):
        body, negative = body[1:-1].strip(), True
    if not DIGITS.match(body):
        raise ValueError("not an amount: %r" % text)
    groups = re.split(r"[.,]", body)
    # The last separator is the decimal point unless exactly three digits follow it, in which
    # case every separator groups thousands.
    if len(groups) > 1 and len(groups[-1]) != 3:
        value = float("".join(groups[:-1]) + "." + groups[-1])
    else:
        value = float("".join(groups))
    return -value if negative else value


def parse_lines(lines):
    """Parse an iterable of ledger lines; return (transactions, errors).

    errors is a list of the malformed lines, stripped, in the order they appeared.
    """
    transactions, errors = [], []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(";")
        try:
            if len(fields) != 3:
                raise ValueError("expected three fields")
            day = datetime.strptime(fields[0].strip(), "%Y-%m-%d").date()
            transactions.append(Transaction(day, fields[1].strip(), parse_amount(fields[2])))
        except ValueError:
            errors.append(line)
    return transactions, errors
