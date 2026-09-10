#!/usr/bin/env python3
"""Art is authored as text in `assets/`; every table both machines use is
generated from it by this tool.

The decision is *2026-09-10 The asset pipeline* in the vault, and issue #48 is
where it stops being a decision and starts being a script. Three reasons it
exists, all of them scars:

* **Bytes are unreviewable.** Nobody can look at `0xDB, 0xDB, 0x7E` and say
  whether the arms are clear of the body. A grid of `#` and `.` is the form a
  person can read, argue with and edit.
* **Two hand-maintained copies always drift.** Until now every sprite was drawn
  twice -- once as hex in `spikes/sprites.py`, once as a grid in
  `assets/sprites/` -- and the only thing keeping them equal was a test that
  compared them. That test could say they disagreed but not which was right.
  Now there is one source and the other is generated.
* **The Z80 gets the same bytes from the same file.** `--python` emits a module
  for the prototype, `--asm` emits `DEFB` tables for the port. An art change is
  one edit and two regenerations, and the two machines cannot disagree about
  what a wall looks like.

**Bit order is the Spectrum's own: bit 7 is the leftmost pixel**, one byte per
row, rows top to bottom -- which is what `core.Screen` models and what the
display file wants, so no converter anywhere reverses anything.

**Deterministic on purpose.** Blocks come out sorted by name and there is no
timestamp in the header, because a timestamp would make every regeneration a
diff and drown the one thing the generated file is committed for: a test
regenerates it into a temporary path and compares byte for byte, so art and
code cannot drift without the suite failing.

What it deliberately does not do (all three from the decision note):

* **No pre-shifting, no masks, no rotation tables.** That expansion belongs to
  the port's sprite routine and depends on a decision nobody has taken; baking
  it into the asset format would bake in the unmade decision. This converts a
  picture into bytes and stops.
* **No colour.** A bitmap has no ink -- hue is per cell and comes from the
  room's palette. An asset that could name a colour would be an asset that
  could break the clash guarantee.
* **No guessing.** Anything it does not understand is an error naming the file,
  the line and the column. A converter that repairs its input quietly is a
  second author.

Usage::

    python tools/bitmaps.py --python prototype/spikes/bitmaps_gen.py \\
        assets/sprites assets/tiles
    python tools/bitmaps.py --asm spectrum/src/bitmaps.asm \\
        assets/sprites assets/tiles

This is a build-time tool. It is not under `prototype/tests/test_portability.py`
-- it is never on a Spectrum -- but it emits integers and nothing else.
"""

import argparse
import os
import re
import sys

#: The two grid characters. `#` sets the pixel, `.` leaves it clear.
INK, CLEAR = "#", "."

#: A block's identity. The file name is documentation; this is the name the
#: generated tables are keyed and labelled by, so it has to be an identifier in
#: Python and a label in Z80 assembly at the same time.
NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

HEADER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.*)$")
SIZE_RE = re.compile(r"^(\d+)x(\d+)$")

#: Everything is 8 pixels wide because an attribute cell is, and a sprite that
#: was not would need a second format rather than more data.
WIDTH = 8

#: People and doors are 8x16; everything else is 8x8. A third height would be a
#: third drawing routine on the Z80, so it is refused here rather than
#: discovered there.
HEIGHTS = (8, 16)


class BitmapError(ValueError):
    """A fault in an asset file, located precisely enough to go and fix.

    File, line and column, because the alternative -- "bad character in grid" --
    sends somebody hunting through sixteen blocks of near-identical art.
    """

    def __init__(self, source: str, line: int, column: int, message: str):
        self.source, self.line, self.column = source, line, column
        where = f"{source}:{line}"
        if column:
            where += f":{column}"
        super().__init__(f"{where}: {message}")


class Block:
    """One named bitmap: its size, its rows as bytes, and its row comments."""

    __slots__ = ("name", "width", "height", "rows", "art", "notes", "source",
                 "line")

    def __init__(self, name, width, height, rows, art, notes, source, line):
        self.name = name
        self.width = width
        self.height = height
        #: One byte per row, bit 7 leftmost.
        self.rows = tuple(rows)
        #: The grid as authored, one string per row -- carried through into the
        #: generated files so that the bytes there can still be read as a
        #: picture without opening the asset.
        self.art = tuple(art)
        #: Whatever the author wrote after column 8 on each row.
        self.notes = tuple(notes)
        self.source = source
        self.line = line

    def __repr__(self) -> str:
        return f"Block({self.name!r}, {self.width}x{self.height})"


def _is_comment(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(";")


def parse_text(text: str, source: str) -> list:
    """Every block in one file, in the order it was written.

    The grammar is small enough to read in one sitting: comments and blank
    lines are furniture, `key: value` lines open a block, and the lines after
    them up to the next blank line are the picture.
    """
    blocks: list = []
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or _is_comment(line):
            index += 1
            continue
        block, index = _parse_block(lines, index, source)
        blocks.append(block)
    return blocks


def _parse_block(lines, index: int, source: str):
    """One block, starting at `index`, which is a header line."""
    start = index
    headers: dict = {}
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            raise BitmapError(source, index + 1, 0,
                              "a block's headers are not followed by a grid")
        if _is_comment(line):
            index += 1
            continue
        match = HEADER_RE.match(line)
        if match is None:
            break
        key, value = match.group(1).lower(), match.group(2).strip()
        if key in headers:
            raise BitmapError(source, index + 1, 1, f"{key} given twice")
        headers[key] = (value, index + 1)
        index += 1
    else:
        raise BitmapError(source, len(lines), 0,
                          "a block's headers are not followed by a grid")

    name = _header_name(headers, source, start)
    width, height = _header_size(headers, source, start)

    rows, art, notes = [], [], []
    while index < len(lines) and lines[index].strip():
        line = lines[index]
        if _is_comment(line):
            index += 1
            continue
        bits, drawn, note = _parse_row(line, index + 1, source, width)
        rows.append(bits)
        art.append(drawn)
        notes.append(note)
        index += 1

    if len(rows) != height:
        raise BitmapError(
            source, index, 0,
            f"{name} says {width}x{height} but has {len(rows)} rows")
    return Block(name, width, height, rows, art, notes, source, start + 1), index


def _header_name(headers, source, start):
    if "name" not in headers:
        raise BitmapError(source, start + 1, 1, "a block needs a name:")
    value, line = headers["name"]
    if not NAME_RE.match(value):
        raise BitmapError(
            source, line, 1,
            f"name {value!r} is not [A-Z][A-Z0-9_]* -- it has to be a Python "
            f"identifier and a Z80 label at the same time")
    return value


def _header_size(headers, source, start):
    if "size" not in headers:
        raise BitmapError(source, start + 1, 1, "a block needs a size: WxH")
    value, line = headers["size"]
    match = SIZE_RE.match(value)
    if match is None:
        raise BitmapError(source, line, 1,
                          f"size {value!r} is not WxH, e.g. 8x16")
    width, height = int(match.group(1)), int(match.group(2))
    if width != WIDTH:
        raise BitmapError(
            source, line, 1,
            f"width {width} -- everything is {WIDTH} wide, because an "
            f"attribute cell is")
    if height not in HEIGHTS:
        raise BitmapError(
            source, line, 1,
            f"height {height} -- people and doors are 8x16 and everything "
            f"else is 8x8, so it must be one of {HEIGHTS}")
    return width, height


def _parse_row(line: str, number: int, source: str, width: int):
    """One grid row: its byte, the grid itself, and any row comment.

    **Anything after column `width` is a row comment and is ignored**, provided
    a space separates it. That is how the art annotates itself -- `##.##.##
    arms clear of the body` -- and losing it would make these files worse than
    the docstrings they replace.
    """
    if len(line) < width:
        raise BitmapError(
            source, number, len(line) + 1,
            f"the row is {len(line)} characters and needs {width}")
    grid = line[:width]
    for column, char in enumerate(grid, start=1):
        if char not in (INK, CLEAR):
            raise BitmapError(
                source, number, column,
                f"{char!r} is not {INK!r} or {CLEAR!r}")
    rest = line[width:]
    if rest and not rest[0].isspace():
        raise BitmapError(
            source, number, width + 1,
            "a row comment must be separated from the grid by a space")
    bits = 0
    for i, char in enumerate(grid):
        if char == INK:
            bits |= 1 << (width - 1 - i)
    return bits, grid, rest.strip()


# --- reading a tree ---------------------------------------------------------

def read_tree(paths, root: str = "") -> list:
    """Every block under every path given, sorted by name.

    **Names are unique across the whole tree**, not per file: the file name is
    documentation and the name is the identity, so a duplicate is an error
    rather than a silent overwrite of one picture by another.
    """
    blocks: list = []
    for path in paths:
        full = os.path.join(root, path) if root else path
        for source in sorted(_asset_files(full)):
            label = os.path.relpath(source, root) if root else source
            text = open(source, encoding="utf-8").read()
            blocks.extend(parse_text(text, label.replace(os.sep, "/")))
    seen: dict = {}
    for block in blocks:
        first = seen.get(block.name)
        if first is not None:
            raise BitmapError(
                block.source, block.line, 1,
                f"{block.name} is already used by {first.source}:{first.line} "
                f"-- a name is the identity and has to be unique across the "
                f"whole tree")
        seen[block.name] = block
    return sorted(blocks, key=lambda b: b.name)


def _asset_files(path: str):
    if os.path.isdir(path):
        for base, _dirs, files in os.walk(path):
            for name in files:
                if name.endswith(".txt"):
                    yield os.path.join(base, name)
    else:
        yield path


# --- emitting ---------------------------------------------------------------

def _sources_line(paths) -> str:
    """The source directories, as the generated header names them."""
    return ", ".join(p.replace(os.sep, "/").rstrip("/") for p in paths)


def _sources_cmd(paths) -> str:
    """The same, as they were given on the command line, so the regenerate
    line in the header can be copied and run rather than edited first."""
    return " ".join(p.replace(os.sep, "/").rstrip("/") for p in paths)


def python_module(blocks, paths) -> str:
    """The prototype's table, as a module.

    A tuple per block plus `BITMAPS`, and the grid carried through as a comment
    beside each byte so the generated file can still be read as a picture.
    """
    sources, command = _sources_line(paths), _sources_cmd(paths)
    out = [
        '"""Bitmaps, generated by tools/bitmaps.py. Do not edit.',
        "",
        f"Source: {sources}. Regenerate with::",
        "",
        f"    python tools/bitmaps.py --python <this file> {command}",
        "",
        "Bit 7 is the leftmost pixel, one byte per row, rows top to bottom --",
        "the Spectrum's own order, which is what `core.Screen` models.",
        "",
        "There is no timestamp here on purpose: this file is committed, and a",
        "test regenerates it and compares byte for byte, so any diff at all is",
        "art and code having drifted.",
        '"""',
        "",
    ]
    for block in blocks:
        out.append(f"{block.name} = (")
        for bits, art, note in zip(block.rows, block.art, block.notes):
            comment = f"  # {art}" + (f"   {note}" if note else "")
            out.append(f"    0x{bits:02X},{comment}")
        out.append(")")
        out.append("")
    out.append("#: Every bitmap by name, for the tools and tests that want to")
    out.append("#: walk them all.")
    out.append("BITMAPS = {")
    for block in blocks:
        out.append(f'    "{block.name}": {block.name},')
    out.append("}")
    out.append("")
    return "\n".join(out)


def asm_module(blocks, paths) -> str:
    """The port's table, as plain `DEFB` lines.

    Plain because every Z80 assembler in use accepts them, and the assembler
    is still an open decision -- nothing here should foreclose it.
    """
    sources, command = _sources_line(paths), _sources_cmd(paths)
    out = [
        "; Bitmaps, generated by tools/bitmaps.py. Do not edit.",
        ";",
        f"; Source: {sources}. Regenerate with::",
        ";",
        f";     python tools/bitmaps.py --asm <this file> {command}",
        ";",
        "; Bit 7 is the leftmost pixel, one byte per row, rows top to bottom.",
        "; No timestamp: the file is committed and a test compares it byte for",
        "; byte, so any diff is art and code having drifted.",
        "",
    ]
    for block in blocks:
        out.append(f"{block.name}:")
        for bits, art, note in zip(block.rows, block.art, block.notes):
            comment = f"; {art}" + (f"   {note}" if note else "")
            out.append(f"        DEFB ${bits:02X}                   {comment}")
        out.append("")
    return "\n".join(out)


def write_if_changed(path: str, text: str) -> bool:
    """Write, and say whether anything moved. Returns True if it did."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if os.path.exists(path) and open(path, encoding="utf-8").read() == text:
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python tools/bitmaps.py",
        description="Generate bitmap tables from the text art in assets/.")
    parser.add_argument("--python", default=None,
                        help="write a Python module here")
    parser.add_argument("--asm", default=None,
                        help="write Z80 DEFB tables here")
    parser.add_argument("--root", default="",
                        help="directory the source paths are relative to, "
                             "and what the generated header names them by")
    parser.add_argument("sources", nargs="+",
                        help="asset directories or files")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if not args.python and not args.asm:
        print("nothing to do: give --python, --asm, or both", file=sys.stderr)
        return 2
    try:
        blocks = read_tree(args.sources, args.root)
    except BitmapError as bad:
        print(bad, file=sys.stderr)
        return 1
    if not blocks:
        print(f"no blocks found in {_sources_line(args.sources)}",
              file=sys.stderr)
        return 1

    for path, text in ((args.python, python_module(blocks, args.sources)),
                       (args.asm, asm_module(blocks, args.sources))):
        if path:
            changed = write_if_changed(path, text)
            print(f"{path}: {len(blocks)} bitmaps"
                  f"{'' if changed else ' (unchanged)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
