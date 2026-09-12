"""Categorisation of transactions by ordered keyword rules."""

DEFAULT_RULES = (("rewe", "groceries"), ("market", "groceries"), ("salary", "income"),
                 ("rent", "housing"), ("netflix", "subscriptions"))


def categorise(description, rules=None, fallback="other"):
    """Return the category of the first matching rule, else the fallback."""
    text = description.lower()
    for keyword, category in (DEFAULT_RULES if rules is None else rules):
        if keyword.lower() in text:
            return category
    return fallback
