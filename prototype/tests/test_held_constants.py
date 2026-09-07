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

from spikes import clegs, rescue, scene, session, sources, spray


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


def test_the_nest_constants_are_untouched():
    """Never measured, because a body had never once lain on screen. Now that
    one does -- the clocks are staggered and the run outlives the first death --
    they can be, and that is the nest work's job rather than this issue's.

    `BODY_FRAMES` is the prototype's stand-in for the twenty-second window the
    vault specifies. It is ten seconds, and it is *not* the agreed number: it
    is what the spike left behind and nothing has yet been built that reads it.
    Recorded here so the discrepancy is found on purpose rather than by
    surprise when nests are built.
    """
    assert rescue.BODY_FRAMES == 500
