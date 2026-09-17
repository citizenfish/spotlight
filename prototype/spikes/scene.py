"""The playtest building: two rooms, one doorway, and no key.

**Since issue #107 this module is a view.** The building is authored in
`assets/levels/level3.txt` and loaded by `levels.py`; every name here --
`ROOM_A`, `WORKERS_A`, `PLAYER_START`, `BUILDING` and the rest -- reads
the loaded level, so the tests and the bots that grew up on these names go
on working. The docstrings below explain *why* the rooms are shaped as they
are, which the file does not repeat. The legend lives in `building.py`:

    #  wall        D  the way out of the building (its own hue)
    .  floor       K  key (the hue of the door it opens)
    d  doorway (floor, drawn with returns -- issue #48)

**Four characters, and every one of them says what a cell is made of** (issue
#50). Room lights are not in the map and never were properly: they are
authored beside it, as rectangles -- see `LIGHTS_B`. The cost of that is real
and worth naming here rather than in a commit message: you can no longer read
this file and see the light sitting on the doorway, and you have to look in two
places. The map used to be the whole picture of a room. What it bought is that
a light and a doorway can share a cell, which they do, and neither has to move.

**There is no key.** Doors and keys are not built, so a `K` would be a magenta
glyph that could not be picked up and opened nothing. The legend and the hue
stay, because a key is a real thing in *Building Structure* and the colour rule
is worth keeping exercised.

**The two rooms differ in floor hue and in nothing else** (issue #47): room A's
floor is yellow, room B's is cyan, and every wall in the building is white. See
`FLOOR_A` for why the floor is what carries it.

--- what issue #21 changed, and why ----------------------------------------

Until now there was one room, and the far side of every wall in it was still on
screen. That is why *The Playtest Building* asks for a second room rather than a
bigger one: the moment the design's sharpest claim depends on -- your tail
strung out behind you somewhere you cannot cover -- has nowhere to happen in a
room you can see all of at once.

* **Room A keeps its shape**, so that the measurements taken against it stay
  comparable. What moved: the way out is now in the **west** wall, the
  connecting doorway is in the **east**, and the wall across row 18 is gone.
* **Room B is the opposite of A on every dial the author has.** No searchlight,
  one authored room light, and it sits on the doorway home.
* **Population is the building's, not the room's.** Clegs cross doorways and go
  to light, so a room's authored count is not its worst case: the whole swarm
  can be in the room you are standing in.

  **The budget is sized for the worst plausible failure, not the opening state**
  (issue #33) -- the swarm, one nest's full brood, the nest, the player and the
  largest tail the level can produce. **In T-states, not Cleg-equivalents**
  (issue #34): a ceiling denominated in one entity's cost moves whenever that
  entity's sprite format does, and cell-aligned Clegs moved it. This building
  comes to **30,274 against 32,832 -- 92%, and it fits.** See
  `Building.worst_case`, and `session.Session._load` for the valve that enforces
  it at the moment it would be broken.
"""

from spotlight.core.constants import CYAN, YELLOW

from .building import (
    CONSTANT_INK, DOOR, DOORWAY, EXIT, FLOOR, KEY, SOLID, WALL, palette,
)
from . import levels as levels_mod

#: Level 3, the playtest building, loaded once (issue #107).
_LEVEL = levels_mod.level(levels_mod.SCENE_LEVEL)


def building(level: int, seed: int = levels_mod.DEFAULT_SEED):
    """The building of level `level` for run `seed` (issues #109, #120).
    `BUILDING` is the default level's for the default seed; every other
    level, and every other roll, is reached through here."""
    return levels_mod.level(level, seed)

#: Which room is which, as indices. Room A is 0 because the player starts there.
NEAR, FAR = 0, 1

#: **The floor carries the room and the walls carry the building** (issue #47).
#:
#: The floor is the biggest lit area on screen and it is visible the moment any
#: light falls anywhere, so it is the cheapest place to read *which room am I
#: in* -- the one thing every tester so far has been unable to hold. The walls
#: keep WHITE in both rooms because they mean "solid", which is a fact about the
#: building and not about the room.
#:
#: Sprites take the hue of the cell they stand in, as they always have, so
#: everybody in A is yellow and everybody in B is cyan. Colour has never been
#: allowed to tell entities apart (*Avoiding attribute clash*), and telling you
#: which room you are in is the strongest use left for it.
#:
#: **The price, said plainly: cyan spray on room B's cyan floor.** The two are
#: told apart by pattern -- droplets against the four-dot stipple -- and not by
#: hue. It is the one collision this palette produces and it buys cyan meaning
#: exactly one thing everywhere else in the building.
#:
#: **Two coloured rooms is all the palette holds.** Once RED, MAGENTA, GREEN,
#: CYAN and WHITE are spoken for, YELLOW is the only free ink left, so the rule
#: to author by is that a hue identifies a *floor of the building* rather than
#: a room: rooms meant to feel like one place share one, and two rooms that
#: share a hue must not be adjacent.
FLOOR_A, FLOOR_B = YELLOW, CYAN

#: The two palettes, authored beside the maps they colour.
INK_A = palette(FLOOR_A)
INK_B = palette(FLOOR_B)

#: Which rows the connecting doorway occupies, in **both** rooms. Three cells
#: tall: two would fit a person, but the movement assist nudges by up to a cell
#: and a door the player bounces off is the first thing this audience reads as
#: broken. It changes no rule -- one-cell doorways stay legal, and room A's
#: inner box still has one.
DOOR_ROWS = (10, 11, 12)

#: Room A's shape.
#:
#: Three things about it are issue #21's and are worth reading off the picture:
#:
#: 1. **The exit is the two `D` cells in the west wall**, at rows 10 and 11. It
#:    used to be a single cell in the *top* wall. Two cells because a person is
#:    two cells tall and one cell wide, so a one-cell gap in a **vertical** wall
#:    is a gap nobody fits through -- you cannot stand in it, and `deliver` asks
#:    whether your body touches the door. The old rule ("a doorway one cell
#:    across is passable") was written when the only doorway in the prototype
#:    was in a horizontal wall, and it does not carry over.
#: 2. **The connecting doorway is the gap in the east wall** at rows 10-12. It
#:    is `d` rather than a `D`: `D` is the way *out of the building* and
#:    carries the exit's hue, and the vault is explicit that the hue rule is for
#:    *locked* doors, which have to announce that a key exists. This one is
#:    unlocked and announces itself another way -- see the shouts. `d` is floor
#:    in every mechanical respect and changes only the picture (issue #48): it
#:    draws returns, so the gap reads as a doorway rather than as a room that
#:    stops there. The inner box's one-cell door at (15, 7) is the other one,
#:    and it is the case the character was added for.
#: 3. **The wall across row 18 is gone**, and a short wall at column 24 stands
#:    in its place. The old wall sealed the bottom-right corner: Clegs steer and
#:    slide rather than pathfind, so they piled against it and never arrived,
#:    and a motionless player there lost 1.6 blood in 150 seconds against 146.2
#:    in the middle -- ninety-one times safer, and the strongest play in the
#:    game. Measured with the Cleg's own steering rule (not a flood fill: a
#:    flood fill asks whether a path exists, which is the wrong question about
#:    something that cannot find one), the corner cells could be arrived at from
#:    15% of the room's floor. With the wall turned on its side they are at 24%,
#:    which is ordinary, and the wall still detours the journey rather than
#:    merely decorating it.
#: **Furnished 2026-09-16** (Look and feel 3 row 6, issue #102): every
#: character that changed was a `#` and every one is still solid, so the
#: solidity bitmaps the furniture tests hold are unchanged -- 151 and 157
#: -- and no log can move. Room A's low wall is a crate, a desk and a crate;
#: its long wall a pipe run; its right-hand column a riser. Room B's six
#: thin columns are risers -- which is what ends the ladder read three
#: reviews called -- and its four blocks are desks over cabinets round
#: crates. The user placed nothing; the retro-gamer's review chose the cells.
ROOM_A = _LEVEL[NEAR].rows

#: Room B's shape: the dark room.
#:
#: **The room light is not in this picture and it used to be** -- it is
#: `LIGHTS_B`, the three cells at column 0, rows 10 to 12, and it covers the
#: three `d` cells at the far left, which are B's side of the doorway home. Read
#: the two together; that is the price issue #50 paid to let one cell be both a
#: doorway and lit. What the light does for the level is under `LIGHTS_B`.
#:
#: **The three cells at column 0 are `d`, and getting them there is what issue
#: #50 was for.** Issue #48 built every doorway in the building except this one
#: and stopped here: the cells were `LLL`, a cell holds one character, and
#: marking them `d` would have taken three cells out of the light's zone and
#: moved its origin from (1, 11) to (2, 11) -- a lure moved to make a picture
#: right, which that slice was forbidden to do. The refusal was correct and the
#: fix was to stop asking the map where the light is. **Nothing about the light
#: moved: the zone is the same rectangle, the origin is the same cell.** The
#: opening now draws its returns, so the way home reads as a doorway from both
#: sides instead of looking like a room that stops there from one of them.
#:
#: The furniture is partitions and machinery blocks, all of them open at both
#: ends. That is not taste. Concave shapes -- an alcove, a recess whose mouth
#: faces the wrong way, a wall that seals a corner -- are permanent refuges,
#: because a Cleg steers greedily and slides and cannot find its way round one.
#: An earlier draft of this room had three-sided bays down each side and they
#: measured at 3-9% swarm reach, worse than the bottom-right corner that this
#: issue exists to remove. As drawn, **no floor cell in B can be arrived at from
#: fewer than 22% of B's floor**, and none at all is unreachable.
ROOM_B = _LEVEL[FAR].rows

#: Room B's room lights: one, at (left, top, width, height) = (0, 10, 3, 3).
#:
#: **Authored beside the map rather than painted into it** (issue #50). Until
#: then it was an `LLL` block in `ROOM_B` and this rectangle was reconstructed
#: from it at load; the rectangle is identical, and that it is identical is the
#: point -- what a light reaches and where the swarm gathers did not move, and
#: it is the acceptance criterion of the issue that let the doorway be drawn.
#:
#: **It sits on the doorway back to A.** *Light and Darkness* calls the room
#: light the level author's sharpest tool and no room in the prototype had ever
#: authored one, so this is the least-exercised path in the lighting code and
#: the centrepiece of the level at the same time. It does three things:
#:
#: * From anywhere in B you can see the way home, so B is navigable without
#:   being safe. Room lights show the building and never the people in it, so
#:   finding the four workers is still entirely your problem.
#: * **A permanent light is a permanent lure**, so the one route you have to use
#:   is the one place the swarm reliably gathers. The lure is the middle of the
#:   zone -- (1, 11), which is what a Cleg steers at -- and it is why nothing
#:   was allowed to move this rectangle by a column to make a picture work.
#: * B is never wholly black on re-entry, so going back for a look costs
#:   curiosity rather than progress.
#:
#: What it does **not** do is make your tail prey while it files through. The
#: vault's worked example says it should; *Light and Darkness* says room lights
#: reveal nobody, to Clegs exactly as to the player, and that rule is agreed,
#: argued at length and enforced by `LightField.prey_at`. The agreed rule wins
#: here and the contradiction is the designer's to settle. What the level gets
#: instead is nearly as sharp: the swarm gathers at the door, and the moment you
#: light your own tail to see it across, the whole line is prey with the flies
#: already standing there.
#:
#: **Room A authors none**, which is why there is no `LIGHTS_A`: A is the room
#: with the searchlight, and the two rooms are opposites on every dial the
#: author has.
LIGHTS_B = _LEVEL[FAR].lights

#: What each room is called when a report has to say where somebody was lost.
#: Words a person would use, because the user reads them out to a playtester who
#: is trying to remember: *you lost the one in the far room at about a minute --
#: did you know they were there?*
NEAR_NAME = _LEVEL[NEAR].name
FAR_NAME = _LEVEL[FAR].name


# `INNER_DOOR`, the one-cell doorway of room A's inner box at (15, 7), went
# when the room began to roll (issue #121): a rolled room has no pocket by
# construction, and `test_spike_tiles` draws a one-cell doorway on a boxed
# room of its own.

#: Which entity kinds move. Movers are only drawn where a light is on them this
#: frame; the rest are fixtures the fade is allowed to remember.
#:
#: Named by `sprites.SPRITES` key, and the Cleg has two of them since it gained
#: a second wing frame (issue #49). `ENTITIES` is empty, so nothing in the game
#: reads this today; it is kept in step anyway, because a lookup that has been
#: wrong for a while is worse than one that has never been used.
MOVERS = frozenset({"worker", "cleg_a", "cleg_b"})

#: Fixed scenery, for the whole building. **Empty on purpose.** A body and a
#: nest were placed while sprites were the question in spike 1, and they stayed
#: long after they meant anything -- two objects on screen that could not be
#: reached, sprayed or rescued. Bodies come from workers who bleed out, and
#: since issue #33 nests come from bodies nobody reached; neither is scenery and
#: neither is authored. The list stays because the drawing code and its tests
#: are about the *kinds* of thing a room holds, not about these two.
ENTITIES = ()

#: What the exit sign says, and it is always on.
EXIT_SIGN = "EXIT"

# --- the clock ladder -------------------------------------------------------
#
# **Blood is authored, never computed and never rolled.** Every worker used to
# start on the same blood and bleed on the same tick, so all seven died in the
# same frame: there was no "who do I go to first", no death anybody could learn
# from, and no body ever lay on screen because the level ended on the frame they
# were created.
#
# 30/40/50/60/70/80/90 against `rescue.BLEED_EVERY` of 100 frames gives lives of
# **60, 80, 100, 120, 140, 160 and 180 seconds** -- twenty seconds between
# consecutive deaths, which is one body window each.
#
# **Which worker gets which rung is assigned by journey, not by room** -- issue
# #21 overturns an earlier instruction that the far room takes the shortest
# clocks. The rule is *the nearest is the least urgent*:
#
# * A short clock on somebody beside you is not a decision. You simply go.
# * A short clock on the furthest person is not a decision either. It is a loss
#   you were never offered, because the distance already carries the stake.
# * The person you can *just* reach if you leave now, and will be badly out of
#   position afterwards, is where a clock does its work.
#
# So urgency belongs at the **middle** distance, and the consequence was not
# designed and is better than what was: **room A is where the clock bites and
# room B is where the journey does.** Going into B is a decision about distance
# and darkness; staying in A is a decision about time. Two lessons for one door.

#: Room A's three. A first-timer who never finds the doorway ends on three of
#: seven, which is the top of the target band -- **the near room is worth three
#: by construction.** All three positions are kept from the seven the one-room
#: build had, so the room stays recognisably itself.
WORKERS_A = _LEVEL[NEAR].workers

#: Room B's four, spread away from the doorway. Their clocks are the four
#: longest, because every one of them is a journey through two rooms and back
#: and the distance is already the stake.
WORKERS_B = _LEVEL[FAR].workers

#: Where the swarm starts, in cells. **Three per room, six in the building**,
#: which is what the prototype has always had; the nine that appeared in an
#: earlier draft of the vault note was a proposal that got quoted back as a
#: fact. Six is what two concurrent nests cost a room that also has to hold two
#: broods. What headroom that leaves is counted in `building.py`, in T-states:
#: this building's worst plausible failure is 92% of a frame's entity budget,
#: and the hold-the-spawn valve is what holds it there.
#:
#: Spread wide and none of them near the player, so a swarm has to travel and
#: you hear it coming long before it arrives.
CLEGS_A = _LEVEL[NEAR].clegs
CLEGS_B = _LEVEL[FAR].clegs

# `SPOTLIGHTS_A` and `SPOTLIGHTS_B` -- the floor lamps the torch was swapped
# for, a decent one and a trap in A and the strongest in the building deep in
# B -- went with the torch (issue #119).

#: Where the player starts.
#:
#: **Not on the exit**, and that is a deliberate omission rather than an
#: oversight. *Building Structure* settled on 2026-09-07 that the player starts
#: at the exit, because that is where they came in and where death returns them.
#: Moving the start onto the door would land on top of a question the designer
#: is currently ruling on -- a Wanderer already ends its run in under two
#: seconds on three seeds in twelve by walking into the exit by accident, and
#: putting the start *on* the door makes that certain rather than likely. Issue
#: #21 does not ask for the start to move and the ruling should land on its own
#: terms, so the start stays where it has been measured.
#:
#: Two things the first attempt got wrong and which still hold: the whole 8x16
#: box has to clear the walls rather than just the cell the coordinates land in,
#: and the start should have room in every direction rather than be tucked under
#: a wall.
PLAYER_START = _LEVEL[NEAR].player_start

#: Room A's searchlight.
#:
#: **`repeat`, not `vary`, and that is an authoring choice per light rather than
#: a rule change** (issue #23). Repeating is "the easier setting, and it makes
#: the searchlight a puzzle -- you can watch it, time it, and cross behind it",
#: where varying is weather. The beam turned out to deliver about three quarters
#: of the swarm, and the dominant threat in the game should be something a
#: first-timer can learn.
#:
#: With the connecting doorway in the east wall, the beam now runs over it: the
#: beam runs to the wall rather than turning short of it, so the way through is
#: intermittently lit, and lit ground gathers the swarm. That is free level
#: design and it is why the doorway is in A rather than anywhere else.
#:
#: The radius is **not** an authoring choice being made here. Three was settled
#: by a person at a keyboard -- at twice that the beam was over you before you
#: could do anything about it -- and it is held.
SEARCHLIGHT_RADIUS = _LEVEL[NEAR].searchlight.radius
SEARCHLIGHT_VARY = _LEVEL[NEAR].searchlight.vary


#: The building the game is played in: **Level 3, loaded from
#: `assets/levels/level3.txt`** (issue #107). The file is the source and
#: every name in this module is a view of it, kept so the tests and the bots
#: that read `scene.ROOM_A` and its kin go on reading the same tuples. One
#: instance, loaded at import, because the authored data never changes
#: during a run -- on the Z80 it is ROM.
BUILDING = _LEVEL

#: The two rooms by name, for the code and the tests that want to say which.
ROOM_NEAR = BUILDING[NEAR]
ROOM_FAR = BUILDING[FAR]


def validate() -> None:
    """The building must line up, or nothing else does."""
    BUILDING.validate()
    if len(WORKERS_A) + len(WORKERS_B) != 7:
        raise ValueError("the playtest building is seven people")


__all__ = [
    "BUILDING", "building", "CLEGS_A", "CLEGS_B", "CONSTANT_INK", "DOOR_ROWS",
    "ENTITIES",
    "EXIT",
    "EXIT_SIGN", "FAR", "FAR_NAME", "FLOOR", "FLOOR_A", "FLOOR_B", "INK_A",
    "INK_B", "KEY",
    "DOOR", "DOORWAY", "MOVERS", "NEAR", "NEAR_NAME", "PLAYER_START",
    "ROOM_A",
    "ROOM_B",
    "LIGHTS_B", "ROOM_FAR", "ROOM_NEAR", "SEARCHLIGHT_RADIUS",
    "SEARCHLIGHT_VARY", "SOLID", "WALL",
    "WORKERS_A", "WORKERS_B", "validate",
]
