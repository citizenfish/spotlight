"""The constants issue #23 deliberately did **not** move, and their reasons.

Holding a number is a decision and it gets a test, because the tempting mistake
is to move the one that was blamed loudest. Every assertion here is paired with
why the value stayed, so that a future reader can judge whether the reason still
holds rather than only that somebody once wrote the number down.

This file is not a list of things that may never change. It is a list of things
that must not change *by accident*, or as a side effect of tuning something
else. If one of these should move, the way to move it is to argue it in the
vault, raise an issue, and edit this file in the same commit as the constant.
"""

from spikes import building, clegs, rescue, scene, session, sources, spray


def test_cleg_hunger_was_cut_in_half_and_it_bought_nothing():
    """`KEEN_MAX` is the one constant this file has released. Issue #25 cut it
    from twelve to six, **the prediction it was cut on was falsified, and the
    cut was reverted.**

    It was held here once, because it had been named as *the* tuning dial on
    the strength of a measured 1.0x that turned out to be a window artefact.
    Issue #25 was a different diagnosis -- an absolute baseline rather than a
    ratio -- and it predicted that halving the cap would take the dark
    thirty-second cost from 33.2 to 18-20, leave the lit cost near 49.6, and
    push a dark first bite past twenty seconds.

    Measured on five seeds with the driver: **33.2, 49.6 and 13.6 seconds.
    Every one of them to the digit, unchanged.** See the test below for the
    arithmetic that made the first two impossible, and `test_spike_clegs.py`
    for the run that pins it.

    **The value goes back to twelve**, because a change is a claim and a
    falsified claim does not get to leave its change behind. Six was defensible
    as a reach and indefensible as a difficulty decision, and a later reader
    finding a six would reasonably assume somebody had tuned it. Twelve is
    where the person who built and judged hunger put it, with their reason
    beside it.

    **Hunger is not the dial**, and the reason is in the attribution hook from
    #22: a dark, motionless player's blood is billed almost entirely to the
    searchlight, which is lit, mobile and noticeable from anywhere, and
    therefore wins the nearest-lure comparison long before the glow's extra
    cells matter.
    """
    assert clegs.KEEN_MAX == 12


def test_the_cap_cannot_move_a_thirty_second_number_at_all():
    """Why the cut measured as an exact no-op, in one line of arithmetic.

    Keenness is `hunger // HUNGER_STEP`, so a fly needs
    `KEEN_MAX * HUNGER_STEP` frames of not feeding to reach the cap -- and at
    six cells that is 1500 frames, which is the entire thirty-second window the
    prediction was stated over. **Inside that window a cap of six and a cap of
    twelve are the same number**, because neither is ever reached. The two
    predicted figures could not have moved whatever the swarm did.

    The assertion is written against six rather than the current twelve on
    purpose: it is the *cut* that had to clear this bar, and it did not.

    This is the check that was not done before the constant was proposed, and
    it costs nothing to keep. If the cap is ever cut again to move a
    thirty-second baseline, this fails and says why.
    """
    window = 30 * 50
    assert 6 * clegs.HUNGER_STEP >= window
    assert clegs.KEEN_MAX * clegs.HUNGER_STEP >= window


def test_the_beam_keeps_its_speed_and_its_size():
    """Both settled by a person at a keyboard -- *"at twice that it was over you
    before you could do anything about it"* -- and nothing measured implicates
    either. A bot's number does not outrank a play report.

    Six frames a cell is about eight cells a second: slow enough to watch, time
    and cross behind. Three was tried and played too fast to do anything about.
    """
    assert sources.Roaming(0, 0).step_every == 6
    assert scene.SEARCHLIGHT_RADIUS == 3


def test_blood_stays_at_sixty_four_in_eight_pips():
    """One bite is one pip, so a player can count what a swarm cost them.

    Note that it *saturates* against three lives over a long stationary run,
    which is why blood totals over long windows are a bad measure. That is a
    problem with the target, not with the number.
    """
    assert session.BLOOD_FULL == 64
    assert session.BLOOD_FULL // clegs.DRAIN_TOTAL == 8


def test_lives_stay_at_three():
    assert session.LIVES == 3


def test_the_spray_keeps_five_charges_and_a_five_second_patch():
    """The nest arithmetic in the vault depends on both, and it already says
    the right thing: five charges against a twenty-second body window."""
    assert spray.Spray().charges == 5
    assert spray.PATCH_FRAMES == 5 * 50


def test_the_body_window_moved_to_the_number_the_vault_agreed():
    """**The discrepancy this file was keeping, collected.**

    `BODY_FRAMES` was 500 -- ten seconds -- against a vault that had agreed
    twenty. It was the spike's leftover and nothing read it, so it was pinned
    here rather than quietly corrected, on the rule that a number should be
    found on purpose rather than by surprise. Issue #33 is the work that reads
    it, so this is where it moves.

    The nest constants beside it are new and are not held: they are derived
    from the spray, not chosen against it. See `rescue.NEST_SPAWN_EVERY`.
    """
    assert rescue.BODY_FRAMES == 20 * 50
    assert rescue.NEST_FRAMES == 30 * 50
    assert rescue.GONE_FRAMES == 50 * 50


def test_the_playtest_building_is_over_the_entity_ceiling():
    """**Counted here, and refused nowhere.** The number, and why it is a
    finding rather than a bug fix.

    Issue #33 asks that level validation be sized for a level's **worst
    plausible failure** rather than its opening state, because a nest is the
    first thing in the game that manufactures entities. Counted that way -- the
    authored swarm, one nest's full brood, the nest, the player and the largest
    tail the level can produce -- the playtest building comes to 25.25
    Cleg-equivalents against a ceiling of eighteen.

    **And it was already over before nests existed.** Six flies, the player and
    a tail of six is 18.25, and nobody had counted it: the figure quoted in
    `scene.py` and in `test_spike_doorway.py` is 14.75, which assumes a tail of
    four. Eighteen and a seven-person building have been in tension since issue
    #21 and the tension is arithmetic, not a nest.

    Nothing is refused on it, and that is the issue's own wording rather than a
    softening: *"the valve, which is now the budget's only guarantee"*. A nest
    whose spawn would take the room over the ceiling holds it -- see
    `session.Session._nests` -- so the ceiling is enforced at the moment it
    would be exceeded rather than by refusing to start.

    **What to do about it is a decision for the vault**, and there are three
    levers, all of them authored numbers somebody argued for: the size of the
    swarm, the number of people in the building, and the ceiling itself. This
    test exists so that whichever one moves, it moves on purpose.
    """
    b = scene.BUILDING
    assert b.worst_case() == 101, "the worst plausible failure moved"
    assert b.over_budget == 101 - building.ENTITY_CEILING
    # Before a single nest turns, and this is the part that is not about nests.
    assert building.cost(clegs=b.population, people=1 + b.largest_tail) \
        > building.ENTITY_CEILING
