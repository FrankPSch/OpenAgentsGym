from fail import scale


def test_origin():
    assert scale(0) == 0


def test_scale_two_is_five():
    assert scale(2) == 5


def test_scale_two_is_six():
    assert scale(2) == 6
