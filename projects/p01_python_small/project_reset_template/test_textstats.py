from textstats import word_frequencies


def test_counts_words_case_insensitively():
    assert word_frequencies("The cat, the CAT and a dog.") == {
        "cat": 2, "the": 2, "a": 1, "and": 1, "dog": 1}


def test_strips_surrounding_punctuation_and_keeps_apostrophes():
    assert word_frequencies("Hello, hello! don't -- don't") == {"don't": 2, "hello": 2}


def test_ties_are_ordered_by_word_ascending():
    assert list(word_frequencies("b a b a c").items()) == [("a", 2), ("b", 2), ("c", 1)]


def test_empty_string():
    assert word_frequencies("") == {}
