"""Aggregation per month and category, and the text report."""

from decimal import ROUND_HALF_UP, Decimal

from ledger.rules import categorise


def round_half_away(value, places=2):
    """Round half away from zero to `places` decimals; return a float."""
    return float(Decimal(repr(value)).quantize(Decimal(1).scaleb(-places),
                                               rounding=ROUND_HALF_UP))


def aggregate(transactions, rules=None):
    """Return {(month, category): rounded total} with month written YYYY-MM."""
    totals = {}
    for transaction in transactions:
        key = (transaction.date.strftime("%Y-%m"), categorise(transaction.description, rules))
        totals[key] = totals.get(key, 0.0) + transaction.amount
    return dict((key, round_half_away(total)) for key, total in totals.items())


def format_report(totals):
    """Render the aggregate as one `YYYY-MM;category;amount` line per entry."""
    return "\n".join("%s;%s;%.2f" % (month, category, totals[(month, category)])
                     for month, category in sorted(totals))
