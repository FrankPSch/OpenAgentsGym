"""Order intake and stock allocation: read two feeds, price them, allocate, report."""


class FeedError(Exception):
    """A feed cannot be read at all: wrong header, wrong version, duplicate key."""
