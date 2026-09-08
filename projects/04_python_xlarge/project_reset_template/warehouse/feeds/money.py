"""Money as whole cents: parsing, rounding, formatting."""


def parse_money(text):
    """Parse an amount written with a comma decimal separator; return whole cents.

    Raises ValueError when the text is not an amount.
    """
    raise NotImplementedError


def round_half_away(cents, unit=1):
    """Round a cent amount to the nearest multiple of `unit`, halves away from zero."""
    raise NotImplementedError


def format_money(cents):
    """Render whole cents as a plain decimal string with two places and a dot."""
    raise NotImplementedError
