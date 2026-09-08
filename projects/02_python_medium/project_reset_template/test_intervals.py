from intervals import IntervalSet, contains, merge, total_length


def test_merge_empty():
    assert merge([]) == []


def test_merge_single():
    assert merge([[1, 3]]) == [[1, 3]]


def test_merge_overlapping():
    assert merge([[1, 5], [3, 7]]) == [[1, 7]]


def test_merge_adjacent():
    assert merge([[1, 2], [3, 4]]) == [[1, 4]]


def test_merge_leaves_gap():
    assert merge([[1, 2], [4, 5]]) == [[1, 2], [4, 5]]


def test_merge_unsorted_input():
    assert merge([[5, 6], [1, 2], [3, 4]]) == [[1, 6]]


def test_merge_contained():
    assert merge([[1, 10], [3, 4]]) == [[1, 10]]


def test_total_length_empty():
    assert total_length([]) == 0


def test_total_length_disjoint():
    assert total_length([[1, 2], [4, 5]]) == 4


def test_total_length_overlapping():
    assert total_length([[1, 5], [3, 7]]) == 7


def test_contains_inside_and_boundary():
    assert contains([[1, 5], [8, 9]], 1) is True
    assert contains([[1, 5], [8, 9]], 5) is True
    assert contains([[1, 5], [8, 9]], 9) is True


def test_contains_outside():
    assert contains([[1, 5], [8, 9]], 6) is False
    assert contains([], 0) is False


def test_set_empty():
    s = IntervalSet()
    assert list(s) == []
    assert len(s) == 0
    assert 0 not in s


def test_set_add_merges_adjacent_and_overlapping():
    s = IntervalSet([[1, 2]])
    s.add([3, 4])
    s.add([4, 7])
    assert list(s) == [[1, 7]]


def test_set_add_keeps_gaps_and_iterates_ascending():
    s = IntervalSet()
    s.add([8, 9])
    s.add([1, 2])
    assert list(s) == [[1, 2], [8, 9]]


def test_set_len_is_total_length():
    s = IntervalSet([[1, 5], [3, 7], [10, 10]])
    assert len(s) == 8


def test_set_contains_boundaries_and_gaps():
    s = IntervalSet([[1, 5], [8, 9]])
    assert 1 in s and 5 in s and 9 in s
    assert 6 not in s and 0 not in s


def test_set_remove_splits_interval_in_two():
    s = IntervalSet([[1, 10]])
    s.remove([4, 5])
    assert list(s) == [[1, 3], [6, 10]]
    assert len(s) == 8


def test_set_remove_trims_edges_and_drops_covered():
    s = IntervalSet([[1, 5], [8, 9]])
    s.remove([4, 8])
    assert list(s) == [[1, 3], [9, 9]]


def test_set_remove_outside_is_a_no_op():
    s = IntervalSet([[1, 5]])
    s.remove([7, 9])
    assert list(s) == [[1, 5]]
    assert len(s) == 5
