"""The asset pipeline: art is authored as text, and every table is generated.

Issue #48, from *2026-09-10 The asset pipeline*.

**What was wrong before.** Every sprite in the game was drawn twice -- once as
hex in `spikes/sprites.py`, once as a grid in `assets/sprites/` -- and the only
thing holding them together was a test that compared them. That test could say
they had drifted; it could never say which of the two was right, and it could
not help the Z80 at all, which had no copy and would have got a third.

There is one source now. These tests are what makes that claim true rather than
merely intended:

* **the committed tables regenerate byte for byte from `assets/`**, so a `.txt`
  edited without regenerating fails the suite; and
* **the Python and the assembly agree byte for byte**, so the two machines
  cannot be given different art.

The converter's refusals get a test each, because a converter that guesses is a
second author. Every one of them names the file, the line and the column.
"""

import importlib.util
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "bitmaps.py"
ASSETS = ("assets/sprites", "assets/tiles")

#: Where the generated tables are committed. Both are in the repository so that
#: a clone builds and runs without the tool ever being executed.
GENERATED_PY = ROOT / "prototype" / "spikes" / "bitmaps_gen.py"
GENERATED_ASM = ROOT / "spectrum" / "src" / "bitmaps.asm"


def _tool():
    """`tools/bitmaps.py`, loaded by path.

    It lives outside `prototype/` because it is a build-time tool and not part
    of the game, so it is not on the test suite's import path and is loaded
    here rather than installed.
    """
    spec = importlib.util.spec_from_file_location("bitmaps_tool", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bitmaps = _tool()


def parse(text: str, source: str = "test.txt"):
    return bitmaps.parse_text(text, source)


BLOCK = """\
; a comment, and a blank line after it

name: THING
size: 8x8
##......   two set, six clear
........
#......#
........
........
........
........
.......#
"""


# --- the format -------------------------------------------------------------

def test_bit_seven_is_the_leftmost_pixel():
    """The Spectrum's own order, so no converter anywhere reverses anything.

    It is worth pinning rather than assuming: get it backwards and every sprite
    in the game is mirrored, which is invisible on the symmetric ones -- the
    player, the worker, the Cleg -- and only shows up on the body.
    """
    block, = parse(BLOCK)
    assert block.name == "THING"
    assert block.rows[0] == 0xC0, "'##......' is the top two bits"
    assert block.rows[2] == 0x81
    assert block.rows[7] == 0x01, "'.......#' is bit 0"


def test_a_row_comment_is_kept_for_the_reader_and_ignored_for_the_bytes():
    """`##.##.##   arms clear of the body` is how the art annotates itself.

    Losing it would make these files worse than the docstrings they replace, so
    the comment survives into the generated module beside the byte it explains
    while contributing nothing to it.
    """
    block, = parse(BLOCK)
    assert block.notes[0] == "two set, six clear"
    assert block.notes[1] == ""


def test_two_blocks_in_one_file_are_separated_by_a_blank_line():
    text = BLOCK + "\n" + BLOCK.replace("THING", "OTHER")
    names = [b.name for b in parse(text)]
    assert names == ["THING", "OTHER"]


def test_people_are_8x16_and_everything_else_is_8x8():
    tall = "name: TALL\nsize: 8x16\n" + "........\n" * 16
    block, = parse(tall)
    assert block.height == 16 and len(block.rows) == 16


# --- the refusals, each naming file, line and column ------------------------

def _fails(text, source="art.txt"):
    with pytest.raises(bitmaps.BitmapError) as caught:
        parse(text, source)
    return caught.value


def test_a_character_that_is_not_hash_or_dot_is_an_error_at_its_column():
    """**The converter never guesses.** A typo in a grid is somebody's art
    silently coming out wrong, and the point of authoring art as text is that
    a person can see what they drew."""
    bad = "name: THING\nsize: 8x8\n" + "........\n" * 3 + "..x.....\n" + \
        "........\n" * 4
    error = _fails(bad)
    assert error.source == "art.txt"
    assert error.line == 6, "the line the bad character is on"
    assert error.column == 3, "the column it is in"
    assert "'x'" in str(error)


def test_a_duplicate_name_anywhere_in_the_tree_is_an_error(tmp_path):
    """The file name is documentation; `name` is the identity. Two blocks with
    one name would mean one picture silently overwriting another."""
    (tmp_path / "a.txt").write_text(BLOCK)
    (tmp_path / "b.txt").write_text(BLOCK)
    with pytest.raises(bitmaps.BitmapError) as caught:
        bitmaps.read_tree([str(tmp_path)])
    assert "THING" in str(caught.value)
    assert "unique" in str(caught.value)


def test_the_wrong_number_of_rows_is_an_error():
    short = "name: THING\nsize: 8x8\n" + "........\n" * 7
    error = _fails(short)
    assert "7 rows" in str(error)


def test_a_width_that_is_not_eight_is_an_error():
    error = _fails("name: THING\nsize: 6x8\n" + "......\n" * 8)
    assert "width 6" in str(error)
    assert error.line == 2


def test_a_height_that_is_not_eight_or_sixteen_is_an_error():
    error = _fails("name: THING\nsize: 8x12\n" + "........\n" * 12)
    assert "height 12" in str(error)


def test_a_row_that_is_too_short_is_an_error():
    error = _fails("name: THING\nsize: 8x8\n" + "........\n" * 7 + "....\n")
    assert "4 characters" in str(error)


def test_a_row_comment_must_be_separated_from_the_grid():
    """Otherwise a nine-character row is a typo that reads as a comment."""
    error = _fails("name: THING\nsize: 8x8\n" + "........x\n"
                   + "........\n" * 7)
    assert error.column == 9


def test_a_block_without_a_name_or_a_size_is_an_error():
    assert "name:" in str(_fails("size: 8x8\n" + "........\n" * 8))
    assert "size:" in str(_fails("name: THING\n" + "........\n" * 8))


def test_a_name_that_is_not_an_identifier_is_an_error():
    """It has to be a Python name and a Z80 label at the same time."""
    error = _fails("name: little thing\nsize: 8x8\n" + "........\n" * 8)
    assert "not [A-Z]" in str(error)


# --- deterministic ----------------------------------------------------------

def test_blocks_come_out_sorted_by_name_whatever_order_they_were_read(tmp_path):
    (tmp_path / "z.txt").write_text(BLOCK.replace("THING", "ZED"))
    (tmp_path / "a.txt").write_text(BLOCK.replace("THING", "ALPHA"))
    names = [b.name for b in bitmaps.read_tree([str(tmp_path)])]
    assert names == sorted(names) == ["ALPHA", "ZED"]


def test_there_is_no_timestamp_in_either_output():
    """A timestamp would make every regeneration a diff, and the whole value of
    committing the generated file is that a diff means something."""
    for text in (GENERATED_PY.read_text(), GENERATED_ASM.read_text()):
        assert not re.search(r"\d{4}-\d{2}-\d{2}", text)
        assert not re.search(r"\d{2}:\d{2}:\d{2}", text)


# --- the committed tables are the assets ------------------------------------

def _regenerate(kind: str) -> str:
    blocks = bitmaps.read_tree(ASSETS, str(ROOT))
    emit = bitmaps.python_module if kind == "python" else bitmaps.asm_module
    return emit(blocks, ASSETS)


def test_the_committed_python_module_is_what_the_assets_generate():
    """**This test is the decision.** Without it the pipeline is just a script.

    If it fails, somebody edited a `.txt` and did not regenerate, or edited the
    generated module by hand. Either way art and code have drifted, and the fix
    is::

        python tools/bitmaps.py --python prototype/spikes/bitmaps_gen.py \\
            --asm spectrum/src/bitmaps.asm assets/sprites assets/tiles
    """
    assert GENERATED_PY.read_text() == _regenerate("python")


def test_the_committed_asm_table_is_what_the_assets_generate():
    assert GENERATED_ASM.read_text() == _regenerate("asm")


def test_the_asm_and_the_python_hold_the_same_bytes():
    """**The same source feeds both machines**, and this is where that is
    checked rather than asserted. The two files are read back independently and
    compared label by label and byte by byte."""
    from spikes import bitmaps_gen

    from_asm: dict = {}
    label = None
    for line in GENERATED_ASM.read_text().splitlines():
        line = line.split(";")[0].strip()
        if not line:
            continue
        if line.endswith(":"):
            label = line[:-1]
            from_asm[label] = []
            continue
        match = re.fullmatch(r"DEFB \$([0-9A-F]{2})", line)
        assert match, f"not a plain DEFB line: {line!r}"
        from_asm[label].append(int(match.group(1), 16))

    assert {k: tuple(v) for k, v in from_asm.items()} == bitmaps_gen.BITMAPS


def test_every_bitmap_the_game_draws_came_out_of_the_pipeline():
    """Sprites and tiles both, so that neither can quietly grow a second copy."""
    from spikes import bitmaps_gen, sprites, tiles

    for sprite in sprites.SPRITES.values():
        assert tuple(sprite) in set(bitmaps_gen.BITMAPS.values())
    for table, prefix in ((tiles.WALL_LIT, "WALL_LIT"),
                          (tiles.WALL_DIM, "WALL_DIM"),
                          (tiles.DOORWAY, "DOORWAY")):
        for mask, rows in enumerate(table):
            assert rows == bitmaps_gen.BITMAPS[f"{prefix}_{mask:02d}"]


def test_writing_only_happens_when_something_changed(tmp_path):
    """Small, and it is what keeps `--python` safe to run from a script: a
    regeneration that changes nothing must not touch the file's mtime and set
    every watcher going."""
    path = str(tmp_path / "out.py")
    assert bitmaps.write_if_changed(path, "one\n") is True
    assert bitmaps.write_if_changed(path, "one\n") is False
    assert bitmaps.write_if_changed(path, "two\n") is True
