"""Entry point: ``python -m spotlight`` from the prototype/ directory.

**This is the one command a player is given**, so it has to start the game.
Until issue #14 it started the walking skeleton in ``core.game`` -- a blob of
light moving round an empty grid -- while the game itself was
``python -m spikes.spike1``. Anybody handed the obvious command played the
wrong program and concluded the game was a dot.

So this module delegates, and the delegation direction is deliberately the
awkward way round: ``spotlight`` reaches into ``spikes``. That is backwards
(``spikes`` imports ``spotlight.core``, not the other way about) and it is
temporary. The spike is still the spike; what has changed is only which command
reaches it. When the architecture replaces ``spikes/``, this file gains a real
runner and loses the import.

The skeleton is still in ``core.game`` and still tested -- it proves the 50Hz
loop end to end -- it is simply no longer what the entry point reaches.
"""

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # Imported here rather than at module scope so that importing
    # ``spotlight.__main__`` does not drag pygame in behind it.
    from spikes import spike1

    return spike1.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
