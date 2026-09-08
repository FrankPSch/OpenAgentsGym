"""Small text statistics helpers."""

from collections import Counter
from string import punctuation


def word_frequencies(text):
    """Count words in text, lowercased and stripped of surrounding punctuation.

    Returns a dict ordered by count descending, then by word ascending.
    """
    counts = Counter(w for w in (t.strip(punctuation).lower() for t in text.split()) if w)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
