"""Closed integer intervals, written [start, end] with start <= end."""


def merge(intervals):
    """Merge overlapping and adjacent intervals; return them sorted ascending by start."""
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def total_length(intervals):
    """Number of integers covered by the merged intervals."""
    return sum(end - start + 1 for start, end in merge(intervals))


def contains(intervals, x):
    """True when the integer x lies inside any of the intervals."""
    return any(start <= x <= end for start, end in intervals)


class IntervalSet(object):
    """A mutable set of integers held as merged, ascending closed intervals."""

    def __init__(self, intervals=None):
        self.intervals = merge(intervals or [])

    def add(self, interval):
        """Add [start, end], merging it into the intervals already held."""
        self.intervals = merge(self.intervals + [list(interval)])

    def remove(self, interval):
        """Remove every integer of [start, end]; a removal from the middle splits an interval."""
        low, high = interval
        kept = []
        for start, end in self.intervals:
            if start < low:
                kept.append([start, min(end, low - 1)])
            if end > high:
                kept.append([max(start, high + 1), end])
        self.intervals = kept

    def __contains__(self, x):
        """True when the integer x is in the set."""
        return contains(self.intervals, x)

    def __len__(self):
        """The number of integers in the set, not the number of intervals."""
        return total_length(self.intervals)

    def __iter__(self):
        """Iterate the merged intervals, ascending by start."""
        return iter(self.intervals)
