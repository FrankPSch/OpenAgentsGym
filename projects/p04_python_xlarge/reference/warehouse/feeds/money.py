"""Money as whole cents: parsing, rounding, formatting."""

import re

AMOUNT = re.compile(r"^-?\d+(,\d{1,2})?$")


def parse_money(text):
    """Parse an amount written with a comma decimal separator; return whole cents.

    Raises ValueError when the text is not an amount.
    """
    clean = str(text).strip()
    if not AMOUNT.match(clean):
        raise ValueError("not an amount: %r" % text)
    sign = -1 if clean.startswith("-") else 1
    whole, _, frac = clean.lstrip("-").partition(",")
    return sign * (int(whole) * 100 + int(frac.ljust(2, "0")))


def round_half_away(cents, unit=1):
    """Round a cent amount to the nearest multiple of `unit`, halves away from zero."""
    sign = -1 if cents < 0 else 1
    return int(sign * unit * ((abs(cents) * 2 + unit) // (2 * unit)))


def format_money(cents):
    """Render whole cents as a plain decimal string with two places and a dot."""
    return "%s%d.%02d" % ("-" if cents < 0 else "", abs(cents) // 100, abs(cents) % 100)
