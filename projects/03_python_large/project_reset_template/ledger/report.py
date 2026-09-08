"""Aggregation per month and category, and the text report."""


def round_half_away(value, places=2):
    """Round half away from zero to `places` decimals; return a float."""
    raise NotImplementedError


def aggregate(transactions, rules=None):
    """Return {(month, category): rounded total} with month written YYYY-MM."""
    raise NotImplementedError


def format_report(totals):
    """Render the aggregate as one `YYYY-MM;category;amount` line per entry."""
    raise NotImplementedError
