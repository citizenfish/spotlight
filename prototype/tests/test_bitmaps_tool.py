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

#: The title logo (issue #56) goes through the same tool from the same kind of
#: text art, but into **its own pair of files**, and the separation is the
#: point: it is 128 bytes that are wanted on one screen that is not the game,
#: and on the Spectrum it lives outside the resident set. Generating it into
#: `bitmaps_gen` would put it in the table `sprites`, `tiles` and `floor`
#: import, which is the play path -- see
#: `test_screens.test_the_play_path_does_not_import_the_logo`.
LOGO_ASSETS = ("assets/logo",)
GENERATED_LOGO_PY = ROOT / "prototype" / "spikes" / "logo_gen.py"
GENERATED_LOGO_ASM = ROOT / "spectrum" / "src" / "logo.asm"


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

def _regenerate(kind: str, assets=ASSETS) -> str:
    blocks = bitmaps.read_tree(assets, str(ROOT))
    emit = bitmaps.python_module if kind == "python" else bitmaps.asm_module
    return emit(blocks, assets)


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


def test_the_logo_is_under_the_same_rule_as_every_other_bitmap():
    """The title logo is art, so it is authored as text and generated (#56).

    It is a separate pair of files for a memory reason, not a pipeline one, and
    this is what says so: the same tool, the same format, the same byte-for-byte
    check. If it fails::

        python tools/bitmaps.py --python prototype/spikes/logo_gen.py \\
            --asm spectrum/src/logo.asm assets/logo
    """
    assert GENERATED_LOGO_PY.read_text() == _regenerate("python", LOGO_ASSETS)
    assert GENERATED_LOGO_ASM.read_text() == _regenerate("asm", LOGO_ASSETS)


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
    """Sprites, tiles, and the two stipples, so none can grow a second copy.

    The stipples are here because of issue #51: the wall-tile slice claimed
    nothing that draws declared a byte of its own, and three blocks did -- the
    lit and dim floor stipples and the spray's droplets, the oldest bitmaps in
    the game and therefore the ones a slice looking at walls never saw.
    """
    from spikes import bitmaps_gen, floor, sprites, spray, tiles

    for sprite in sprites.SPRITES.values():
        assert tuple(sprite) in set(bitmaps_gen.BITMAPS.values())
    for table, prefix in ((tiles.WALL_LIT, "WALL_LIT"),
                          (tiles.WALL_DIM, "WALL_DIM"),
                          (tiles.DOORWAY, "DOORWAY")):
        for mask, rows in enumerate(table):
            assert rows == bitmaps_gen.BITMAPS[f"{prefix}_{mask:02d}"]
    assert floor.STIPPLE_LIT == bitmaps_gen.BITMAPS["FLOOR_LIT"]
    assert floor.STIPPLE_DIM == bitmaps_gen.BITMAPS["FLOOR_DIM"]
    assert spray.STIPPLE == bitmaps_gen.BITMAPS["SPRAY"]


# --- the rule, and its one exception, both checked -------------------------

#: Modules under `spikes/` that are allowed to declare bytes, each with the
#: reason it is allowed. **The list is the whole point of the test**: the rule
#: "nothing that draws declares a byte of its own" was stated in a commit
#: message and then had three silent exceptions, and a rule with unlisted
#: exceptions is one nobody can check (issue #51).
BYTE_DECLARERS = {
    "bitmaps_gen.py":
        "the generated table itself -- this is where the bytes are supposed "
        "to be",
    "logo_gen.py":
        "the other generated table (issue #56): the title logo, generated by "
        "the same tool from assets/logo/logo.txt, into a file of its own so "
        "that 128 bytes wanted on one screen are not in the table the play "
        "path imports",
    "font.py":
        "the 8x8 character set. It is genuinely the same kind of thing and "
        "belongs in assets/ too, but it is sixty-odd glyphs keyed by "
        "character -- ':' and '/' and '?' are not [A-Z][A-Z0-9_]* -- so it "
        "needs a naming rule the asset format has not got yet. Issue #51 "
        "scoped itself to the three stipples and left this named here rather "
        "than unnoticed.",
}

#: How many bytes in a row make a declaration rather than a coincidence. Eight
#: is a bitmap's height, and the shortest thing worth moving to `assets/`.
BYTES_IN_A_ROW = 8


def _declared_byte_blocks(path):
    """Every tuple or list in one module that looks like a bitmap.

    Eight or more integer constants, all of them a byte. Read from the syntax
    tree rather than by grepping for `0x`, so that decimal art, a hex constant
    that is not art, and a comment that merely mentions bytes are all judged
    correctly.
    """
    import ast

    found = []
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List)):
            continue
        values = node.elts
        if len(values) < BYTES_IN_A_ROW:
            continue
        if all(isinstance(v, ast.Constant) and isinstance(v.value, int)
               and not isinstance(v.value, bool) and 0 <= v.value <= 0xFF
               for v in values):
            found.append(node.lineno)
    return found


def test_nothing_that_draws_declares_a_byte_of_its_own():
    """The claim the wall-tile slice made, now actually enforced.

    **What was wrong before.** `e651a19` said "nothing that draws declares a
    byte of its own any more" and the drift test only ever looked at the files
    that had already moved, so `floor.py` and `spray.py` went on holding hex
    tuples and `assets/tiles/floor.txt` and `spray.txt` -- both named in the
    asset-pipeline decision -- did not exist. A rule stated in prose and
    checked nowhere is a rule that decays into a habit.

    Anything new that fails this should move its art into `assets/` and
    regenerate. Adding a name to `BYTE_DECLARERS` is allowed, but it is a
    visible decision with a reason attached, which is the difference between an
    exception and a leak.
    """
    spikes = ROOT / "prototype" / "spikes"
    offenders = {}
    for path in sorted(spikes.glob("*.py")):
        if path.name in BYTE_DECLARERS:
            continue
        lines = _declared_byte_blocks(path)
        if lines:
            offenders[path.name] = lines
    assert not offenders, (
        f"{offenders} declares bytes in drawing code. Author the art in "
        f"assets/ and regenerate with tools/bitmaps.py.")


def test_the_stipples_are_inside_the_tree_the_drift_test_watches(tmp_path):
    """Editing a row of `floor.txt` without regenerating must fail the suite.

    The drift test compares the committed module against a regeneration of the
    whole asset tree, so this only holds if `floor.txt` is *in* that tree. That
    is easy to believe and cheap to prove: move one dot in a copy of the tree
    and the regenerated module stops matching the committed one.
    """
    import shutil

    tree = tmp_path / "assets"
    for name in ("sprites", "tiles"):
        shutil.copytree(ROOT / "assets" / name, tree / name)
    floor_txt = tree / "tiles" / "floor.txt"
    text = floor_txt.read_text()
    assert "...#...." in text, "the dim stipple is not where this test looks"
    floor_txt.write_text(text.replace("...#....", "....#...", 1))

    paths = [str(tree / "sprites"), str(tree / "tiles")]
    blocks = bitmaps.read_tree(paths)
    assert bitmaps.python_module(blocks, list(ASSETS)) != GENERATED_PY.read_text()


def test_writing_only_happens_when_something_changed(tmp_path):
    """Small, and it is what keeps `--python` safe to run from a script: a
    regeneration that changes nothing must not touch the file's mtime and set
    every watcher going."""
    path = str(tmp_path / "out.py")
    assert bitmaps.write_if_changed(path, "one\n") is True
    assert bitmaps.write_if_changed(path, "one\n") is False
    assert bitmaps.write_if_changed(path, "two\n") is True
