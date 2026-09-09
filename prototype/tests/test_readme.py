"""The README is an instruction sheet, and instruction sheets go stale silently.

Issue #37. Phase 1 of *Finished prototype* hands this repo to people who have
never seen a Spectrum game and who will follow the front page literally, top to
bottom. Walking it on a fresh clone of `playtest-2` found three faults, and all
three were the same kind of fault: **prose that used to be true**. The dev block
began `pip install -r requirements-dev.txt` as though the reader were at the
repo root, when the block above it had just walked them into `prototype/`, so
the install failed and then `pytest` was `command not found`; its next line,
`cd prototype`, failed for the same reason. And the driver's bot list offered
six bots when `bots.BOTS` had had seven for some time.

Nothing here tests the game. These tests exist so that the page cannot drift
away from the code without the suite saying so, and they pin the two things
that were actually wrong:

  * the names `--bot` is offered, against the registry the driver builds its
    `choices` from, and
  * the directory each shell line is standing in, so a command can never again
    be printed for a reader who is somewhere else.

**What is deliberately not pinned**, because the cost is real and the risk is
not: the key table (arrows, T, space), the `--scale` default of 3, and the
directory tree under *How it is built*. All three would need either a parse of
prose into constants or a second copy of the layout in a test, and none of them
has ever been wrong. If one of them does go wrong, pin it then.
"""

import pathlib
import re

from spikes import bots

ROOT = pathlib.Path(__file__).resolve().parents[2]
README = ROOT / "README.md"

#: A fenced ```sh block, without its fences.
BLOCK = re.compile(r"```sh\n(.*?)```", re.S)


def _text() -> str:
    return README.read_text()


def _offered_bots() -> set[str]:
    """The bot names the README's `--bot` sentence offers.

    The sentence wraps across lines, so whitespace is collapsed before it is
    matched; the names are the backticked words between "takes" and the
    semicolon that ends the clause.
    """
    prose = " ".join(_text().split())
    clause = re.search(r"`--bot` takes (.+?);", prose)
    assert clause, "README no longer has a sentence saying what `--bot` takes"
    return set(re.findall(r"`([a-z_]+)`", clause.group(1)))


def test_the_readme_offers_every_bot_the_driver_accepts():
    """The list on the page and `bots.BOTS` must be the same set.

    The driver takes its `--bot` choices from `sorted(bots.BOTS)`, so adding a
    bot silently widens what the tool accepts while the page keeps advertising
    the old roster -- which is exactly how `undertaker` came to be runnable and
    undocumented. Failing here names the offender in both directions: a bot
    added to the code and not to the page, and a bot named on the page that the
    driver would reject.
    """
    offered = _offered_bots()
    have = set(bots.BOTS)
    missing = sorted(have - offered)
    surplus = sorted(offered - have)
    assert not missing and not surplus, (
        "README's --bot list is out of step with bots.BOTS: "
        f"missing from the README {missing or 'none'}; "
        f"named in the README but not a bot {surplus or 'none'}"
    )


def _walk_the_shell_blocks():
    """Replay every ```sh line in order, tracking the directory.

    The reader follows the blocks as one sequence, so the tests do too. The
    walk starts undefined and takes its bearing from the `cd` into the freshly
    cloned repo, which is this checkout; every later `cd` moves relative to
    that. Yields `(cwd, line)` for each command line, cwd being a real path in
    this checkout.
    """
    cwd = None
    for block in BLOCK.findall(_text()):
        for raw in block.splitlines():
            line = raw.split("#")[0].strip()
            if not line:
                continue
            if cwd is None:
                # Everything before the clone's `cd` happens outside the repo.
                if re.fullmatch(r"cd spotlight", line):
                    cwd = ROOT
                continue
            target = re.fullmatch(r"cd (\S+)", line)
            if target:
                cwd = (cwd / target.group(1)).resolve()
            yield cwd, line


def test_every_directory_the_readme_walks_into_exists():
    """`cd` printed for a reader who is somewhere else is the whole of #37.

    The dev block used to repeat `cd prototype` after the play block had
    already done it, which asks for `prototype/prototype`. Walking the blocks
    in sequence is the only way to catch that, because each line on its own is
    fine.
    """
    for cwd, line in _walk_the_shell_blocks():
        if line.startswith("cd "):
            assert cwd.is_dir(), (
                f"README walks into {cwd}, which does not exist; "
                f"the line is {line!r}"
            )


def test_every_file_the_readme_installs_from_is_where_it_says():
    """`pip install -r X` has to resolve from the directory the reader is in.

    This is the line that failed on the fresh clone: `requirements-dev.txt` is
    at the repo root and the reader was inside `prototype/`. Spelling it
    `../requirements-dev.txt` is what fixed it, and this is what stops it
    reverting to the root-relative spelling next time the block is edited.
    """
    seen = 0
    for cwd, line in _walk_the_shell_blocks():
        named = re.search(r"pip install -r (\S+)", line)
        if not named:
            continue
        seen += 1
        path = (cwd / named.group(1)).resolve()
        assert path.is_file(), (
            f"README says {line!r} from {cwd}, but {path} is not there"
        )
    assert seen == 2, f"expected both pip installs on the page, found {seen}"


def test_every_module_the_readme_runs_is_importable_from_there():
    """`python -m X` needs X on the path, which means the right directory.

    Neither `python -m spotlight` nor `python -m spikes.spike_driver` works
    from the repo root; both want `prototype/`, because the package is not
    installed and `pytest.ini` only sets `pythonpath` for the suite. Checking
    the top-level package is a directory beside the reader is the cheap version
    of that, and it catches a block that has drifted a level.
    """
    seen = 0
    for cwd, line in _walk_the_shell_blocks():
        named = re.search(r"python3? -m ([\w.]+)", line)
        if not named:
            continue
        package = named.group(1).split(".")[0]
        if package == "venv":
            continue
        seen += 1
        assert (cwd / package).is_dir(), (
            f"README says {line!r} from {cwd}, but there is no {package}/ there"
        )
    assert seen == 2, f"expected both `python -m` lines, found {seen}"
