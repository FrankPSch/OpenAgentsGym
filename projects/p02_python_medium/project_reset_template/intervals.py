"""Closed integer intervals, written [start, end] with start <= end."""


def merge(intervals):
    """Merge overlapping and adjacent intervals; return them sorted ascending by start."""
    raise NotImplementedError


def total_length(intervals):
    """Number of integers covered by the merged intervals."""
    raise NotImplementedError


def contains(intervals, x):
    """True when the integer x lies inside any of the intervals."""
    raise NotImplementedError


class IntervalSet(object):
    """A mutable set of integers held as merged, ascending closed intervals."""

    def __init__(self, intervals=None):
        raise NotImplementedError

    def add(self, interval):
        """Add [start, end], merging it into the intervals already held."""
        raise NotImplementedError

    def remove(self, interval):
        """Remove every integer of [start, end]; a removal from the middle splits an interval."""
        raise NotImplementedError

    def __contains__(self, x):
        """True when the integer x is in the set."""
        raise NotImplementedError

    def __len__(self):
        """The number of integers in the set, not the number of intervals."""
        raise NotImplementedError

    def __iter__(self):
        """Iterate the merged intervals, ascending by start."""
        raise NotImplementedError
