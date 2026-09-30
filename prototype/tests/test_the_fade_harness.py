"""A light field is a pure function of its writes. This is the proof.

Issue #148, step 1, and **nothing of step 2 is written until this fails on a
field that is deliberately wrong.** The slice it was split out of wants to stop
decaying a far room's field every frame and age it on demand instead --
`Session._light` commits every room every frame, and a decaying commit is a
704-byte pass, most of 40,401 T-states a far room a frame against 52,416
spendable. That is the single biggest item in the light budget and the reason the
honest room ceiling is two rather than nine.

**The theorem.** The fade is a monotone countdown of one a frame and a source's
top-up is a `max`, so a cell's charge is determined by the writes into it. Nothing
else can move it.

**What the original attempt got wrong, and why this records a schedule rather
than a frame number.** Three things break a naive `charge - (now - stamp)`:

1. **`linger` is a parity term and not a halving.** It bumps solid cells by one
   on even frames only, so a wall's net decay is one per two frames -- and it
   **refuses the bump once decay has taken a cell to zero**, so a cell dies on the
   even frame it enters holding one. A closed form that does not model that death
   has every remembered wall off by one for the rest of its life.
2. **Held frames decay nothing.** The opening holds the game for hundreds of
   frames with `commit(decay=False)` throughout, so elapsed *frames* and elapsed
   *decays* are different numbers -- and a run of held frames of odd length flips
   the parity `linger` depends on.
3. `charge` is read directly by the debug clear and by several tests.

So what the replay below consumes is not `(frame, memory)` but the whole tape:
**for each frame, whether the commit decayed, what each source wrote, and whether
`linger` ran and over which cells.** That is the record the real implementation
will have to reconstruct, and getting the tape right is most of the work.
"""

import pytest

from spikes import lighting, session as S, levels
from spotlight.core.constants import COLS
from spikes.layout import PLAY_ROWS

CELLS = COLS * PLAY_ROWS


class Tape:
    """Every write and every schedule decision, one entry a frame a field."""

    def __init__(self):
        #: field id -> list of frames; each frame is
        #: (decayed, {idx: memory}, linger_cells or None)
        self.frames: dict[int, list] = {}
        self.pending: dict[int, dict] = {}

    def wrote(self, field, idx: int, memory: int) -> None:
        cell = self.pending.setdefault(id(field), {})
        if memory > cell.get(idx, 0):
            cell[idx] = memory

    def committed(self, field, decayed: bool) -> None:
        self.frames.setdefault(id(field), []).append(
            (decayed, self.pending.pop(id(field), {}), None))

    def lingered(self, field, cells) -> None:
        tape = self.frames.setdefault(id(field), [])
        if not tape:
            # `linger` before any commit: give it a frame of its own so the
            # schedule keeps its shape.
            tape.append((False, {}, list(cells)))
            return
        decayed, wrote, _ = tape[-1]
        tape[-1] = (decayed, wrote, list(cells))

    def replay(self, field_id: int) -> bytearray:
        """The charge those frames must have produced, from the tape alone."""
        charge = bytearray(CELLS)
        for decayed, wrote, lingered in self.frames[field_id]:
            if decayed:
                for idx in range(CELLS):
                    if charge[idx]:
                        charge[idx] -= 1
                for idx, memory in wrote.items():
                    if memory > charge[idx]:
                        charge[idx] = memory
            if lingered is not None:
                for idx in lingered:
                    c = charge[idx]
                    # **The death clause.** A cell decay has taken to zero is
                    # not bumped, so it dies on the even frame it enters holding
                    # one. This is the line a naive closed form omits.
                    if 0 < c < 0xFF:
                        charge[idx] = c + 1
        return charge


@pytest.fixture
def taped(monkeypatch):
    """Record every field in the game, and check the replay every frame."""
    tape = Tape()
    real_add = lighting.LightField.add
    real_commit = lighting.LightField.commit
    real_linger = lighting.LightField.linger

    def add(self, cx, cy, level=lighting.LIT, memory=lighting.CHARGE_LIT,
            reveals=True, prey=None):
        real_add(self, cx, cy, level, memory, reveals, prey)
        if level > lighting.DARK and 0 <= cx < COLS and 0 <= cy < PLAY_ROWS:
            tape.wrote(self, cy * COLS + cx, memory)

    def commit(self, decay=True, shown=True):
        real_commit(self, decay, shown)
        tape.committed(self, decay)

    def linger(self, solid_cells):
        real_linger(self, solid_cells)
        tape.lingered(self, list(solid_cells))

    monkeypatch.setattr(lighting.LightField, "add", add)
    monkeypatch.setattr(lighting.LightField, "commit", commit)
    monkeypatch.setattr(lighting.LightField, "linger", linger)
    return tape


def check(tape, run) -> int:
    """Every field of `run` against its replay. Returns how many were checked."""
    checked = 0
    for place in run.places:
        field = place.field
        if id(field) not in tape.frames:
            continue
        want = tape.replay(id(field))
        assert bytes(field.charge) == bytes(want), (
            f"room {place.index} at frame {run.frame}: "
            f"{sum(1 for a, b in zip(field.charge, want) if a != b)} cells differ")
        checked += 1
    return checked


def play(level: int, frames: int, seed: int = 1, **kw):
    from spikes import bots
    building = levels.level(level, seed)
    run = S.Session(seed=seed, sound=False, building=building, **kw)
    player = bots.make("listener", seed=seed)
    for _ in range(frames):
        if run.over is not None:
            break
        run.step(player.intent(run))
    return run


# --- the harness must fail on a field that is wrong -------------------------

def test_the_harness_catches_a_field_that_decays_twice(taped, monkeypatch):
    """**The first thing to establish, before anything is optimised.**

    A harness that cannot fail proves nothing, so here it is failing: a field
    whose decay runs twice a frame is the exact shape of mistake a lazy
    reconstruction makes, and the replay must not agree with it.
    """
    real = lighting.LightField.commit

    def twice(self, decay=True, shown=True):
        real(self, decay, shown)
        if decay:
            # The fault expressed in the field's own terms: one extra tick of
            # the ledger. (It used to be an extra `translate` of `charge`, which
            # the lazy field cannot even express -- `charge` materialises from
            # the ledger, so writing to it is overwritten on the next read. A
            # harness has to speak the representation it is guarding.)
            self._decays += 1

    monkeypatch.setattr(lighting.LightField, "commit", twice)
    run = play(3, 120)
    with pytest.raises(AssertionError, match="cells differ"):
        check(taped, run)


def test_the_harness_catches_a_linger_that_bumps_a_dead_cell(taped, monkeypatch):
    """The subtler one, and the reason the tape records a schedule.

    `linger` refuses its bump once decay has taken a cell to zero. A field that
    bumps anyway is off by one on that cell for the rest of its life, and it is
    the single easiest thing to get wrong in a closed form -- so the harness has
    to notice, and does.
    """
    def generous(self, solid_cells):
        charge = self.charge
        for idx in solid_cells:
            if charge[idx] < 0xFF:        # the missing `0 <` is the whole fault
                if self._stale:
                    self._owed[idx] = charge[idx]
                charge[idx] = charge[idx] + 1

    monkeypatch.setattr(lighting.LightField, "linger", generous)
    run = play(3, 200)
    with pytest.raises(AssertionError, match="cells differ"):
        check(taped, run)


# --- and it must agree with the field the game keeps ------------------------

#: A building of `n` rooms snaked across the plan, every neighbour joined.
#:
#: **The acceptance names two, three, six and nine rooms and the game ships
#: none of two or six** -- the ladder goes 3, 4, 5, 7, 9 and skips both. So the
#: harness builds its own, the same way `measurements/lightcost.py` does, which
#: is also the only way to put a *two*-room building in front of it at all.
_ROOM = """
room: r{i}
roll:
segments: 3 5
length: 4 10
pieces: 1 3
band: 6 24
away: 8
clegs: 1
searchlight: 3 repeat
start: {start}
at: {col} {row}
{doors}
"""


def snake(n: int):
    """`n` rooms, three to a row, joined to every neighbour on the grid."""
    grid = [(i % 3, i // 3) for i in range(n)]
    # One person a room at least, since the snake leaves few dead ends and the
    # deal refuses a roster that cannot fill the rooms on a path (issue #143).
    out = ["level: 9\nname: Fade\nbuilding: The Fade Works\n"
           "blood: 64\nspray: 5\nlives: 3\nmagnet: 10\nwake: on\nfade: 2\n"
           "people: " + " ".join(str(90 - 5 * i) for i in range(n)) + "\n"]
    for i, (col, row) in enumerate(grid):
        doors = []
        for j, (c2, r2) in enumerate(grid):
            if i == j:
                continue
            for way, at in (("east", (col + 1, row)), ("west", (col - 1, row)),
                            ("south", (col, row + 1)), ("north", (col, row - 1))):
                if (c2, r2) == at:
                    span = "10-12" if way in ("east", "west") else "14-16"
                    doors.append(f"door: {way} {span} r{j}")
        out.append(_ROOM.format(i=i, col=col, row=row,
                                start="24 96" if i == 0 else "16 80",
                                doors="\n".join(doors)))
    return "".join(out)


def built(n: int, seed: int = 1):
    from spikes import seeds as seeds_mod
    number, name, specs, budget, _shapes = levels.parse(snake(n), "<snake>")
    b = levels.build(specs, "<snake>",
                     roll_seed=seeds_mod.roll_seed(seed, number),
                     people=budget.people,
                     people_seed=seeds_mod.people_seed(seed, number))
    b.level, b.title, b.name, b.budget, b.seed = (
        number, name, budget.building, budget, seed)
    return b


@pytest.mark.parametrize("rooms", (2, 3, 6, 9))
@pytest.mark.parametrize("fade", (1, 2))
def test_every_field_of_a_building_of_any_size_is_its_writes(taped, rooms, fade):
    """The theorem over the room counts the acceptance names, both wall
    memories: **a light field is a pure function of the writes into it.**"""
    from spikes import bots
    building = built(rooms)
    assert len(building.rooms) == rooms
    run = S.Session(seed=1, sound=False, building=building, wall_fade=fade)
    player = bots.make("listener", seed=1)
    for _ in range(300):
        if run.over is not None:
            break
        run.step(player.intent(run))
    lingered = any(cells is not None for tape in taped.frames.values()
                   for _d, _w, cells in tape)
    assert lingered == (fade == 2), \
        f"fade {fade} {'did not linger' if fade == 2 else 'lingered anyway'}"
    assert check(taped, run) >= min(rooms, 2)


@pytest.mark.parametrize("level,rooms", [(1, 3), (3, 3), (6, 5), (9, 9)])
@pytest.mark.parametrize("fade", (1, 2))
def test_every_field_is_its_writes(taped, level, rooms, fade):
    """The theorem, over the room counts the acceptance names and both wall
    memories: **a light field is a pure function of the writes into it.**

    `fade` is the rate divisor, and the two values are the two schedules that
    behave differently: at 2 `linger` runs on even frames and a wall's net decay
    is one per two, at 1 it never runs at all. `wall_fade` on the session is the
    lever the window and the driver use, so this is the game's own switch rather
    than a reach into the budget.
    """
    building = levels.level(level, 1)
    assert len(building.rooms) == rooms, (level, len(building.rooms))
    run = play(level, 400, wall_fade=fade)
    lingered = any(cells is not None for tape in taped.frames.values()
                   for _d, _w, cells in tape)
    assert lingered == (fade == 2), \
        f"fade {fade} {'did not linger' if fade == 2 else 'lingered anyway'}"
    assert check(taped, run) >= 2, "fewer fields checked than rooms"


def test_the_opening_is_in_it(taped):
    """**Held frames decay nothing**, so a run that goes through the opening has
    elapsed frames and elapsed decays as different numbers -- and a held run of
    odd length flips the parity `linger` depends on. A reconstruction that counts
    frames rather than decays is wrong here and nowhere else."""
    run = play(3, 700, strobe=True)
    assert run.frame > S.OPENING_FRAMES // 2, "the run did not reach the opening"
    held = sum(1 for tape in taped.frames.values()
               for decayed, _w, _l in tape if not decayed)
    assert held > 0, "no held frame was recorded, so this proves nothing"
    assert check(taped, run) >= 2


def test_a_write_of_memory_zero_changes_nothing(taped):
    """Acceptance names it. A source may light a cell and remember nothing of
    it -- the held debug view does -- and `max` with zero is the charge."""
    field = lighting.LightField()
    field.begin()
    field.add(4, 4, lighting.LIT, 0)
    field.commit()
    assert field.charge[4 * COLS + 4] == 0
    assert field.level_at(4, 4) == lighting.LIT, "it is lit while the source is on"
    field.begin()
    field.commit()
    assert field.level_at(4, 4) == lighting.DARK, "and remembered for no frames"


def test_a_cell_dies_under_the_bump(taped):
    """Acceptance names it, and it is `linger`'s death clause on its own.

    A solid cell entering an even frame with a charge of one decays to zero and
    is **not** bumped back, so it dies on that frame. One more frame and it is
    still zero: nothing resurrects it.
    """
    field = lighting.LightField()
    solid = [5 * COLS + 5]
    field.begin()
    field.add(5, 5, lighting.LIT, 1)
    field.commit()
    assert field.charge[solid[0]] == 1
    field.begin()
    field.commit()                       # decays 1 -> 0
    field.linger(solid)                  # and refuses the bump
    assert field.charge[solid[0]] == 0, "a dead cell was bumped back to life"
    field.begin()
    field.commit()
    field.linger(solid)
    assert field.charge[solid[0]] == 0
