"""The 8x8 font."""

from spikes import font
from spotlight.core.screen import Screen


def _render(ch: str) -> list[str]:
    s = Screen()
    font.draw_text(s, 0, 0, ch)
    return ["".join("#" if s.point(x, y) else "." for x in range(8))
            for y in range(8)]


def test_glyph_matches_its_bitmap():
    assert _render("B") == [
        "........",
        ".####...",
        ".#...#..",
        ".####...",
        ".#...#..",
        ".#...#..",
        ".####...",
        "........",
    ]


def test_every_glyph_leaves_a_blank_last_column():
    """Adjacent characters must not touch."""
    for ch, rows in font.GLYPHS.items():
        assert all(not (r & 0x01) for r in rows), f"{ch!r} touches its right edge"


def test_unknown_character_draws_the_missing_block():
    s = Screen()
    font.draw_glyph(s, 0, 0, font.GLYPHS.get("~", font.MISSING))
    assert s.point(1, 1), "missing-glyph block should be visible"


def test_draw_text_returns_the_next_column():
    s = Screen()
    assert font.draw_text(s, 3, 0, "BLOOD") == 8


def test_lowercase_is_folded_to_upper():
    assert _render("b") == _render("B")


def test_draw_glyph_only_touches_its_own_cell():
    s = Screen()
    font.draw_glyph(s, 1, 1, font.BAR_FULL)
    assert s.point(8 + 1, 8 + 1)
    assert not s.point(0, 0) and not s.point(16, 16)
