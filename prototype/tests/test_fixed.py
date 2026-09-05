from spotlight.core import fixed


def test_roundtrip():
    for n in (0, 1, 7, 255, -3):
        assert fixed.to_int(fixed.from_int(n)) == n


def test_one_is_unity_under_mul():
    v = fixed.from_int(5)
    assert fixed.mul(v, fixed.ONE) == v


def test_mul_halves():
    assert fixed.to_int(fixed.mul(fixed.from_int(9), fixed.HALF)) == 4


def test_div_inverts_mul():
    a, b = fixed.from_int(12), fixed.from_int(4)
    assert fixed.to_int(fixed.div(a, b)) == 3


def test_rounding_differs_from_truncation():
    threequarters = fixed.ONE * 3 // 4
    assert fixed.to_int(threequarters) == 0
    assert fixed.round_to_int(threequarters) == 1


def test_clamp():
    assert fixed.clamp(-5, 0, 10) == 0
    assert fixed.clamp(50, 0, 10) == 10
    assert fixed.clamp(5, 0, 10) == 5
