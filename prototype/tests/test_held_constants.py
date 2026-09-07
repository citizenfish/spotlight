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


def test_cleg_hunger_is_not_the_dial_it_was_named_as():
    """`KEEN_MAX` was named as *the* tuning dial on the strength of a measured
    1.0x -- light costing no measurable blood over two minutes.

    **That diagnosis has been superseded.** The 1.0x is real and reproduces, but
    it is explained by three timescales rather than by hunger: the torch holds
    twenty seconds, feeding resets a fly's hunger so light front-loads its cost
    and buys a lull, and blood saturates against three lives. Measured over a
    window the size of a decision the bargain is emphatic -- 2.09x at thirty
    seconds, and a factor of six on time to first bite.

    The swarm is delivered by the searchlight, not by hunger: three quarters of
    attachments on a dark, motionless player land within five seconds of the
    beam passing. Changing a constant on a diagnosis that has been superseded
    is how tuning goes wrong. It may still move; it has not earned it.
    """
    assert clegs.KEEN_MAX == 12


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
