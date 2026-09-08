# 01_python_small

## Task

Implement `word_frequencies(text)` in `textstats.py`. It currently raises `NotImplementedError`.

## Specification

Takes a string, returns a dict mapping word to occurrence count.

- Words are compared case-insensitively; the keys are lowercase.
- Leading and trailing punctuation is stripped (`"Hello,"` counts as `hello`); an
  apostrophe inside a word is kept (`don't` stays `don't`).
- Whitespace separates words; tokens empty after stripping are dropped.
- The dict is ordered by count descending, then by word ascending.

`word_frequencies("The cat, the CAT and a dog.")` returns
`{"cat": 2, "the": 2, "a": 1, "and": 1, "dog": 1}`.

## Files

Change `textstats.py`. Do not modify `test_textstats.py`.

## Verification

Run `python -m pytest -q` before you finish; the harness runs the full tier afterwards.
