# 02_python_medium

## Task

Implement the three functions and the class in `intervals.py`. Each currently raises
`NotImplementedError`. They work on closed integer intervals, each written `[start, end]` with
`start <= end`.

## Specification

- `merge(intervals)` — return the intervals merged and sorted ascending by start.
- `total_length(intervals)` — the number of integers covered by the merged intervals.
- `contains(intervals, x)` — whether the integer `x` falls inside any interval.
- `IntervalSet(intervals=None)` — a mutable set of integers held as merged intervals:
  - `add(interval)` — add `[start, end]`, merging it into what is already there.
  - `remove(interval)` — remove every integer of `[start, end]` from the set. A removal from the
    middle of an interval splits that interval in two.
  - `x in s` — whether the integer `x` is in the set.
  - `len(s)` — the number of integers in the set, not the number of intervals.
  - `iter(s)` — the merged intervals, ascending by start.

Adjacency: the intervals are closed and integer-valued, so `[1, 2]` and `[3, 4]` touch with no
integer between them and merge to `[1, 4]`. `[1, 2]` and `[4, 5]` leave the gap `3` and do not
merge.

## Files

Change `intervals.py`. `test_intervals.py` is the visible suite; read it, and do not modify it.

## Verification

Run `python -m pytest -q` before you finish; the harness runs the full tier afterwards.
