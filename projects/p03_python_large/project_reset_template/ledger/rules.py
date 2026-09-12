"""Categorisation of transactions by ordered keyword rules."""

DEFAULT_RULES = (("rewe", "groceries"), ("market", "groceries"), ("salary", "income"),
                 ("rent", "housing"), ("netflix", "subscriptions"))


def categorise(description, rules=None, fallback="other"):
    """Return the category of the first matching rule, else the fallback."""
    raise NotImplementedError
