"""Held-out suite -- never copied into the project_workspace (oam_targetpicture.md ch.11).

Same public contract as test_intervals.py, different inputs: unsorted, duplicate and nested
intervals, a removal that empties the set, boundaries of one-point intervals, and the length of a
set after overlapping adds.
"""
from intervals import IntervalSet, contains, merge, total_length


def test_merge_collapses_duplicates():
    assert merge([[1, 2], [1, 2], [1, 2]]) == [[1, 2]]


def test_merge_nested_intervals():
    assert merge([[1, 20], [5, 6], [7, 8], [19, 25]]) == [[1, 25]]


def test_merge_unsorted_input_with_adjacency_and_gaps():
    assert merge([[10, 12], [7, 8], [1, 2], [3, 4]]) == [[1, 4], [7, 8], [10, 12]]


def test_merge_single_point_intervals():
    assert merge([[4, 4], [5, 5], [7, 7]]) == [[4, 5], [7, 7]]


def test_total_length_counts_each_integer_once():
    assert total_length([[1, 3], [2, 9], [9, 9], [20, 20]]) == 10


def test_contains_on_the_boundaries_of_a_one_point_interval():
    assert contains([[4, 4]], 4)
    assert not contains([[4, 4]], 3)
    assert contains([[1, 2], [6, 9]], 6)
    assert not contains([[1, 2], [6, 9]], 5)
    assert not contains([[1, 2], [6, 9]], 10)


def test_set_len_after_overlapping_adds():
    s = IntervalSet()
    s.add([1, 5])
    s.add([3, 9])
    s.add([9, 9])
    assert list(s) == [[1, 9]]
    assert len(s) == 9


def test_set_adding_what_is_already_there_changes_nothing():
    s = IntervalSet([[2, 4]])
    s.add([2, 4])
    s.add([3, 3])
    assert list(s) == [[2, 4]]
    assert len(s) == 3


def test_set_remove_covering_everything_empties_the_set():
    s = IntervalSet([[3, 5], [9, 11]])
    s.remove([1, 20])
    assert list(s) == []
    assert len(s) == 0
    assert 4 not in s


def test_set_remove_a_whole_interval_and_a_one_point_interval():
    s = IntervalSet([[1, 3], [5, 9], [12, 12]])
    s.remove([5, 9])
    assert list(s) == [[1, 3], [12, 12]]
    s.remove([12, 12])
    assert list(s) == [[1, 3]]
    assert len(s) == 3
