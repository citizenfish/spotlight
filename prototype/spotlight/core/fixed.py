"""8.8 fixed-point arithmetic.

The Z80 has no FPU and no multiply instruction. Anything the prototype computes
with floats is a promise the port cannot keep, so positions, velocities and
light falloff use 8.8 fixed point: a plain int where the low 8 bits are the
fraction. Every operation here maps to something cheap in Z80.
"""

FRAC_BITS = 8
ONE = 1 << FRAC_BITS
HALF = ONE >> 1


def from_int(n: int) -> int:
    return n << FRAC_BITS


def to_int(f: int) -> int:
    """Truncate toward negative infinity, matching an arithmetic shift right."""
    return f >> FRAC_BITS


def round_to_int(f: int) -> int:
    return (f + HALF) >> FRAC_BITS


def mul(a: int, b: int) -> int:
    """Fixed * fixed. On Z80 this is a shift-and-add routine, not free."""
    return (a * b) >> FRAC_BITS


def div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("fixed-point division by zero")
    return (a << FRAC_BITS) // b


def clamp(f: int, lo: int, hi: int) -> int:
    return lo if f < lo else hi if f > hi else f
