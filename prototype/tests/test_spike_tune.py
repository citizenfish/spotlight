"""The two tunes, and the dropout that is the point of them.

Issue #55. Three kinds of test, and they are worth telling apart:

* **The tables are the vault's.** *Music and Sound#The tunes, as data* holds
  the grid, the note table and the two tunes; the tables are transcribed here a
  second time, by hand, from the note rather than from the module, so that a
  typo in either copy fails rather than agreeing with itself. They are a
  reconstruction and are labelled as one in both places -- **overruling them
  costs a table and not a line of code**, and one test below proves that by
  changing one.
* **The dropout is a ruling.** It is driven by the port model's own arithmetic
  and it renders whole half-cycles and nothing shorter. The last of those is
  the ruling, and it is pinned twice: in the integers, and in the samples that
  come out of the synth.
* **Music decides nothing and is heard last.** The event log is byte-identical
  with music on and off over five seeds and two bots, and no frame with a
  click, a tick or an effect in it has music in it.

**What none of this can tell anybody**, said here as well as in the module
because a test file is where somebody looks for evidence: timing jitter is not
modelled. The host renders exact periods at 44.1kHz and the machine flips a bit
from a loop that wobbles by a few T-states, so the prototype's disintegration
is cleaner than the target's and its pitches steadier. Nothing here is evidence
about pitch stability under a variable frame.
"""

import ast
import pathlib

import pytest

from spikes import (
    bots, building, moments as M, report, session as session_mod, sounds,
    spike_sound, tune,
)
from spikes.session import Session


# --- the grid and the tables are the vault's --------------------------------

def test_the_grid_is_the_one_the_note_settled():
    """12 frames a unit, 8 units a bar as 3-3-2, and the two durations.

    The durations are the evidence the grid is the sketch's own: 23s and 25s
    are what its two files were, and a 12-frame unit in a 3-3-2 bar is the only
    simple grid that reproduces both exactly.
    """
    assert tune.UNIT_FRAMES == 12
    assert tune.CELL_UNITS == (3, 3, 2)
    assert tune.BAR_UNITS == 8 and tune.BAR_FRAMES == 96
    assert len(tune.OSTINATO.bars) == 12
    assert tune.OSTINATO.frames == 1152 and tune.OSTINATO.seconds == 23
    assert len(tune.THEME.bars) == 13, "twelve bars and a one-bar tag"
    assert tune.THEME.frames == 1248 and tune.THEME.seconds == 25


def test_every_period_is_the_delay_constant_for_the_pitch_the_note_names():
    """`3_500_000 // hz`, because a delay constant is what the port wants.

    The periods are quoted in the module rather than computed, so this is the
    check that the quotation is right -- against `sounds.period_of`, which is
    the same arithmetic the fourteen effects go through.
    """
    assert tune.PERIODS[tune.REST] == 0
    for index in range(1, len(tune.PERIODS)):
        assert tune.PERIODS[index] == sounds.period_of(tune.NOTE_HZ[index])
    assert tune.PERIODS[tune.A2] == 31818 and tune.NOTE_HZ[tune.A2] == 110
    assert tune.PERIODS[tune.A4] == 7954 and tune.NOTE_HZ[tune.A4] == 440


def test_every_entry_in_every_table_is_an_integer():
    """**So that the port inherits data rather than a performance.** The tune
    that produced the sketch's WAVs is gone; these tables are what replaces
    it, and a table with anything in it that is not a whole number is one the
    assembler cannot be handed."""
    for table in (tune.PERIODS, tune.NOTE_HZ):
        assert all(isinstance(value, int) for value in table)
    for which in (tune.OSTINATO, tune.THEME):
        for bar in which.bars:
            assert len(bar) == len(tune.CELL_UNITS)
            assert all(isinstance(note, int) for note in bar)
            assert all(0 <= note < len(tune.PERIODS) for note in bar)


#: The two tunes as *Music and Sound* writes them, transcribed by hand from the
#: note. A second copy on purpose: the point of a table is that somebody can
#: check it against the design, and a test that read the module would check
#: nothing.
VAULT_OSTINATO = (
    ("A2", "A2", "A2"), ("A2", "A2", "A2"), ("A2", "A2", "A2"),
    ("A2", "A2", "E4"),
    ("A2", "A2", "A2"), ("A2", "A2", "A2"), ("A2", "A2", "A2"),
    ("A2", "A2", "C4"),
    ("G2", "G2", "G2"), ("G2", "G2", "G2"),
    ("A2", "A2", "A2"),
    ("A2", "A2", "A3"),
)

VAULT_THEME = (
    ("A2", "A2", "A2"), ("A2", "A2", "E4"),
    ("A2", "A2", "A2"), ("A2", "A2", "G4"),
    ("A2", "A2", "A2"), ("A2", "A2", "A4"),
    ("A2", "A2", "A2"), ("A2", "A2", "G4"),
    ("G2", "G2", "G2"), ("G2", "G2", "E4"),
    ("A2", "A2", "A2"), ("A2", "A2", "C4"),
    ("A2", "A2", "A3"),
)


@pytest.mark.parametrize("which,vault", [(tune.OSTINATO, VAULT_OSTINATO),
                                         (tune.THEME, VAULT_THEME)])
def test_the_tune_is_the_table_in_the_note(which, vault):
    named = tuple(tuple(tune.NOTE_NAMES[note] for note in bar)
                  for bar in which.bars)
    assert named == vault


def test_the_bass_and_the_motif_take_turns_and_never_sound_together():
    """**A single bit cannot sound two notes**, and there are no chords
    anywhere in either tune. The test is that a frame has one note in it,
    which is the whole of what the sequencer can return -- said out loud
    because it is the reason the idiom was chosen rather than a happy
    accident."""
    for which in (tune.OSTINATO, tune.THEME):
        for frame in range(which.frames):
            note = which.note(frame)
            assert isinstance(note, int)
            assert 0 <= note < len(tune.PERIODS)


def test_the_pedal_leans_on_g_where_the_note_says_and_nowhere_else():
    """The one harmonic movement in twenty-five seconds, in both tunes."""
    for which, bars in ((tune.OSTINATO, (8, 9)), (tune.THEME, (8, 9))):
        leaning = {bar for bar, cells in enumerate(which.bars)
                   if tune.G2 in cells}
        assert leaning == set(bars)


def test_the_unit_is_the_note_and_the_cell_is_the_pitch_it_repeats_on():
    """Three pulses of A2 rather than 720ms of held A2.

    **The one reading in this module that is not a quotation**, and it is
    flagged in `tune.ARTICULATION` as such. A three-unit cell played as one
    tone is a drone, where the idiom the note describes is *a driving bass
    ostinato ... sparse, pulsing* -- and the grid names a unit at all, which a
    per-cell tune would have no use for.
    """
    first = [tune.OSTINATO.note(f) for f in range(tune.UNIT_FRAMES * 3)]
    unit = [tune.A2] * tune.ARTICULATION \
        + [tune.REST] * (tune.UNIT_FRAMES - tune.ARTICULATION)
    assert first == unit * 3


def test_the_motif_answers_in_the_two_unit_cell_and_the_bass_holds_the_threes():
    """Bar 4 of the ostinato: the bass for six units, then E4 for two."""
    bar = 3 * tune.BAR_FRAMES
    sounding = [tune.OSTINATO.note(bar + f) for f in range(tune.BAR_FRAMES)
                if tune.OSTINATO.note(bar + f) != tune.REST]
    assert set(sounding[:6 * tune.ARTICULATION]) == {tune.A2}
    assert set(sounding[6 * tune.ARTICULATION:]) == {tune.E4}


# --- the tunes are data -----------------------------------------------------

def test_changing_a_table_changes_the_render_and_touches_no_code():
    """**The whole reason the tunes are written this way.**

    *Music and Sound#What to listen for* says that if the idiom is wrong the
    fix is not chords -- there are none available -- it is to let the motif
    move further and to break the 3-3-2 more often, and that it costs a
    scratchpad afternoon. This is that claim, executed: a different table
    played by the same `Tune` class gives a different render, and nothing in
    the module knows.
    """
    argued_with = tune.Tune("argued", tuple(
        (tune.A2, tune.A2, tune.A4) if bar % 2 else cells
        for bar, cells in enumerate(tune.OSTINATO_BARS)))
    assert argued_with.frames == tune.OSTINATO.frames
    before = spike_sound.tune_wave(tune.OSTINATO)
    after = spike_sound.tune_wave(argued_with)
    assert len(before) == len(after)
    assert before != after, "the render did not follow the table"


def test_a_tune_holds_no_position_of_its_own():
    """Two readers of the same tune cannot move each other. The place is the
    sequencer's, and the sequencer's place is the clock's."""
    one = tune.Music(tune.OSTINATO)
    two = tune.Music(tune.OSTINATO)
    for _ in range(300):
        one.update()
    assert two.position == 0 and one.position == 300


# --- music yields to everything ---------------------------------------------

def test_music_never_sounds_on_a_frame_the_sonar_owns():
    voice = sounds.Voice(tune.Music(tune.OSTINATO))
    for _ in range(200):
        voice.update(True, False)
        assert voice.kind == sounds.CLICK
        assert not voice.music.slice.sounding
    assert voice.music.taken == 200


def test_music_never_sounds_on_a_frame_the_body_tick_owns():
    voice = sounds.Voice(tune.Music(tune.OSTINATO))
    for _ in range(200):
        voice.update(False, True)
        assert voice.kind == sounds.TICK
        assert not voice.music.slice.sounding
    assert voice.music.taken == 200


def test_music_never_sounds_on_a_frame_an_effect_owns():
    """A sixty-six frame game-over, and not one frame of music in it."""
    voice = sounds.Voice(tune.Music(tune.OSTINATO))
    voice.update(False, False, [(M.SFX_GAME_OVER, 1)])
    frames = sounds.EFFECTS[M.SFX_GAME_OVER].frames
    for _ in range(frames):
        assert voice.kind == sounds.EFFECT
        assert not voice.music.slice.sounding
        voice.update(False, False)
    assert voice.music.taken == frames


@pytest.mark.parametrize("bot", ["listener", "undertaker", "wanderer"])
def test_nothing_is_ever_heard_over_the_music_in_a_real_run(bot):
    """The invariant, over a whole run rather than over a constructed frame:
    a frame has one voice in it and music is the last of them."""
    from spikes import spike_driver

    heard = []
    run = spike_driver.drive(bots.make(bot, seed=3), seed=3,
                             on_sound=lambda r: heard.append(
                                 r.voice.decision()))
    assert heard
    for kind, _sound, _index, _period, halves in heard:
        if kind != sounds.NOTHING:
            assert halves == 0, "the music was heard over something louder"
    assert any(h[4] for h in heard), "no music in the whole run"
    assert run.voice.music.heard + run.voice.music.taken \
        + run.voice.music.starved + run.voice.music.resting == run.frame


# --- the position is the clock's --------------------------------------------

def test_the_position_advances_whether_or_not_the_note_was_heard():
    """**A tune that stretches under load is a different tune.**

    The sequencer's place comes from the frame counter and from nothing else,
    so a silenced tune resumes where it would have been rather than where it
    left off. This is the third of the three traps the ruling names and it is
    the one an engine written the obvious way falls into, because a player
    routine that advances on the frames it plays is one line shorter.
    """
    played = tune.Music(tune.OSTINATO)
    silenced = tune.Music(tune.OSTINATO)
    for frame in range(tune.OSTINATO.frames):
        played.update(clegs=0, free=True)
        # Silenced three different ways: taken by a louder voice, starved by
        # the budget, and both. None of them may move the position.
        silenced.update(clegs=tune.WORST_CLEGS, free=frame % 3 == 0)
        assert played.position == silenced.position == (frame + 1) % 1152
    assert silenced.heard == 0 and played.heard > 0
    # And the note it resumes on is the note it would have been on.
    assert silenced.tune.note(silenced.frame) \
        == played.tune.note(played.frame)


def test_a_frame_the_game_did_not_step_still_advances_the_tune():
    """The music runs through a death's pause, for the same reason the effect
    clock does: the player routine is on the 50Hz interrupt, and the interrupt
    does not stop because the game logic paused. A tune that stopped for half a
    second and picked up where it left off would be the same tune, later."""
    voice = sounds.Voice(tune.Music(tune.OSTINATO))
    for _ in range(40):
        voice.update(False, False)
    at = voice.music.position
    for _ in range(25):
        voice.audio_frame()
    assert voice.music.position == at + 25


# --- the dropout ------------------------------------------------------------

def test_the_leftover_is_the_port_models_own_arithmetic():
    """`52,416 - fixed - 830n`, and neither term is a figure of this module's
    own: the fixed term is the spendable frame less the entity ceiling the
    valve already enforces, and the 830 is what `building` says a Cleg costs,
    so a port measurement moves all of it together."""
    assert tune.SPENDABLE_TSTATES == 52416
    assert tune.FIXED_TSTATES == 19584
    assert tune.WORST_CLEGS == 36
    for clegs in range(0, 60):
        expected = max(0, 52416 - 19584 - building.CLEG_COST * clegs)
        assert tune.leftover(clegs) == expected


def test_the_music_prices_a_cleg_at_what_the_building_says_one_costs():
    """**The regression this file exists to stop coming back** (issue #58).

    From 2026-09-06 to 2026-09-11 this module carried `CLEG_TSTATES = 1654`,
    the pixel-positioned figure, while the drawing budget and the hatching
    valve priced the same fly at 830. The music was budgeted twice as
    pessimistically as the drawing, and three separate alarms on the project
    traced back to that one stale number. So: the leftover moves when
    `building.CLEG_COST` moves, and there is nothing here for it to disagree
    with.
    """
    assert not hasattr(tune, "CLEG_TSTATES"), \
        "the music grew its own copy of a fly's cost again"
    was = building.CLEG_COST
    try:
        building.CLEG_COST = was * 2
        assert tune.leftover(3) == 32832 - 3 * was * 2, \
            "the leftover did not follow the building's price"
    finally:
        building.CLEG_COST = was
    assert tune.leftover(3) == 32832 - 3 * was


def test_the_musics_own_margin_is_a_named_zero_on_the_fixed_term():
    """A margin for the music is defensible; a doubled fly is not.

    *The 48K cycle budget* leaves sound beyond the sonar click unbudgeted, so
    the player routine's own overhead really is unpaid for. But it is the
    speaker routine, which costs the same whatever is on screen, so it belongs
    on the fixed term and not on a fly -- a per-fly margin would claim a
    proportionality nobody has evidence for. **A zero that is counted is a zero
    that can move**: this pins that the arithmetic will find it the day
    somebody measures a real tone loop, rather than it having to be remembered.
    """
    assert tune.MUSIC_OVERHEAD_TSTATES == 0
    assert tune.FIXED_TSTATES == (tune.SPENDABLE_TSTATES
                                  - building.ENTITY_CEILING
                                  + tune.MUSIC_OVERHEAD_TSTATES)
    was = tune.MUSIC_OVERHEAD_TSTATES
    try:
        tune.MUSIC_OVERHEAD_TSTATES = 1000
        # Recomputed the way the module computes it: the margin comes off the
        # leftover once, at every load, and not once per fly.
        fixed = (tune.SPENDABLE_TSTATES - building.ENTITY_CEILING
                 + tune.MUSIC_OVERHEAD_TSTATES)
        for clegs in (0, 5, 20):
            spare = (tune.SPENDABLE_TSTATES - fixed
                     - building.CLEG_COST * clegs)
            assert spare == tune.leftover(clegs) - 1000
    finally:
        tune.MUSIC_OVERHEAD_TSTATES = was


def test_the_worst_case_is_derived_and_not_written_down():
    """Thirty-six, and the thirty-six is arithmetic rather than a quotation.

    The entity ceiling less the player, who is always drawn, divided by a fly.
    It was eighteen while the fly was priced at 1,654 and it doubled when the
    price was corrected -- **not because anything got louder, but because
    cell-alignment made rooms cheaper**, and this is that halving's bill
    arriving in the one place nobody had looked.
    """
    assert tune.WORST_CLEGS == 36
    assert tune.WORST_CLEGS == ((building.ENTITY_CEILING
                                 - building.PERSON_COST)
                                // building.CLEG_COST)
    # One more fly than the worst case would overrun the ceiling the valve
    # enforces, so the worst case really is the most a frame can hold.
    assert building.cost(clegs=tune.WORST_CLEGS, people=1) \
        <= building.ENTITY_CEILING
    assert building.cost(clegs=tune.WORST_CLEGS + 1, people=1) \
        > building.ENTITY_CEILING


def test_at_no_clegs_the_music_is_heard_on_every_frame_it_wants():
    """Nothing on screen, so nothing takes the frame: both tunes play right
    through, and not one frame is starved."""
    for which in (tune.OSTINATO, tune.THEME):
        music = tune.Music(which)
        for _ in range(which.frames):
            music.update(clegs=0, free=True)
        assert music.starved == 0
        assert music.heard + music.resting == which.frames
        assert music.heard > 0


def test_at_the_worst_case_the_music_emits_nothing_at_all():
    """Thirty-six Clegs is what the port model says a room can hold, and at it
    the frame has 2,952 T-states left -- shorter than half a cycle of the
    highest note in the table. **So the music does not stop when the building
    turns against you. It disintegrates, and then it stops.**

    **This test kept its meaning when the fly's price was corrected** (issue
    #58) and that is the point of it: the worst case *is* the ceiling divided
    by the cost, so it moved from eighteen to thirty-six and the property it
    pins -- that a full frame affords no music at all -- did not move at all.
    A property that survives a halved cost is a property; one that needed the
    old cost was an accident.
    """
    assert tune.leftover(tune.WORST_CLEGS) == 2952
    for index in range(1, len(tune.PERIODS)):
        assert tune.half_cycles(tune.leftover(tune.WORST_CLEGS),
                                tune.PERIODS[index]) == 0
    for which in (tune.OSTINATO, tune.THEME):
        music = tune.Music(which)
        for _ in range(which.frames):
            assert not music.update(clegs=tune.WORST_CLEGS).sounding
        assert music.heard == 0
        assert music.starved + music.resting == which.frames


def test_a_frame_renders_whole_half_cycles_and_nothing_shorter():
    """**The ruling, in a test.**

    A frame that affords three half-cycles plays three and then nothing; a
    frame that affords none is silent. The floor is not a matter of taste --
    *a beeper flips a bit or it does not*, and there is no such thing as a
    third of a flip -- so at every load, for every note, what the frame renders
    is a whole multiple of that note's half-cycle or it is zero.
    """
    for clegs in range(0, tune.WORST_CLEGS + 3):
        spare = tune.leftover(clegs)
        for index in range(1, len(tune.PERIODS)):
            period = tune.PERIODS[index]
            half = tune.half_of(period)
            slice_ = tune.Slice(period, tune.half_cycles(spare, period))
            assert slice_.tstates % half == 0
            assert slice_.tstates <= spare
            # And it is the *most* whole half-cycles that fit: the leftover is
            # spent, not budgeted.
            assert spare - slice_.tstates < half


def test_the_rendered_samples_flip_only_on_a_half_cycle_boundary():
    """The same ruling, in the audio rather than in the integers.

    The engine is allowed to stop early and it is not allowed to stop *part
    way*: every flip in a rendered frame lands on a multiple of the note's
    half-cycle, and after the last one the bit is held for the rest of the
    frame. **Holding it is not silence** -- a beeper has no amplitude, so the
    unspent part of a frame is the speaker where the last flip left it, and
    rendering it as zeroes would be a 50Hz amplitude modulation this engine
    does not have.
    """
    for clegs in (0, 1, 5, 9, 12, 16, tune.WORST_CLEGS):
        for index in range(1, len(tune.PERIODS)):
            period = tune.PERIODS[index]
            halves = tune.half_cycles(tune.leftover(clegs), period)
            synth = spike_sound.MusicSynth()
            synth.active = True
            was = synth.level
            block = synth.frame(period, halves)
            assert len(block) == len(spike_sound.SILENT_FRAME)
            flips = _flips(block, was)
            half = spike_sound.samples_of(tune.half_of(period))
            assert len(flips) == halves
            assert flips == [i * half for i in range(halves)]
            assert set(_levels(block)) <= {spike_sound.AMPLITUDE,
                                           -spike_sound.AMPLITUDE}, \
                "a beeper has one loudness and this render invented another"


def test_the_dropout_is_a_staircase_and_not_a_fade():
    """**Do not smooth it**, and this is what not smoothing it looks like.

    The music's slice falls in whole half-cycles as the room fills -- never by
    a fraction, never with an envelope on it, and never below one flip until it
    reaches none. Every instinct says to fade the music out as the frame fills;
    the breaking up is the feature, and a fade would be the convincing guess
    the ruling refuses.
    """
    lengths = [tune.half_cycles(tune.leftover(n), tune.PERIODS[tune.A4])
               for n in range(tune.WORST_CLEGS + 1)]
    assert lengths[0] == 8 and lengths[-1] == 0
    assert lengths == sorted(lengths, reverse=True), "it went back up"
    # No amplitude anywhere in the chain: the only number that moves is a
    # count of flips.
    assert all(isinstance(n, int) for n in lengths)


def test_the_bass_goes_before_the_motif_does():
    """Not designed, and worth knowing before listening.

    A half-cycle of A2 is 15,909 T-states and one of A4 is 3,977, so the room
    takes the bass out of the tune long before it takes the answer. Under load
    the tune loses its floor and keeps its voice. **If that is wrong the fix is
    a table** -- the in-game music becomes sparser still -- and not a kinder
    engine.
    """
    bass = [n for n in range(tune.WORST_CLEGS + 1)
            if tune.half_cycles(tune.leftover(n), tune.PERIODS[tune.A2])]
    motif = [n for n in range(tune.WORST_CLEGS + 1)
             if tune.half_cycles(tune.leftover(n), tune.PERIODS[tune.A4])]
    assert max(bass) == 20 and max(motif) == 34
    assert tune.half_cycles(tune.leftover(0), tune.PERIODS[tune.A2]) == 2, \
        "the bass never gets more than one whole cycle in a frame"


def test_what_a_quiet_frame_actually_affords_is_measured_and_not_assumed():
    """The figures, pinned, because they are the ones to argue with.

    With nothing on screen the music gets 32,832 T-states of a frame's 69,888
    -- 47% of it -- and the rest is the fixed work and the quarter of the frame
    the budget holds back for contention and the interrupt. **That is not a
    silence anybody chose**: it is what *the music takes the leftover* means
    when the leftover is measured rather than invented. The sketch's own curve
    gave the music 95% of a frame with one Cleg about, and *Music and Sound*
    records that curve as invented for the sketch.
    """
    assert tune.FRAME_TSTATES == 69888
    assert tune.leftover(0) == 32832
    assert 100 * tune.leftover(0) // tune.FRAME_TSTATES == 46
    afforded = {tune.NOTE_NAMES[i]: tune.half_cycles(tune.leftover(0),
                                                     tune.PERIODS[i])
                for i in range(1, len(tune.PERIODS))}
    assert afforded == {"G2": 1, "A2": 2, "A3": 4, "C4": 4,
                        "E4": 6, "G4": 7, "A4": 8}


# --- where each tune plays --------------------------------------------------

def test_the_ostinato_plays_in_a_run_from_its_first_frame():
    run = Session(seed=1)
    assert run.voice.music.tune is tune.OSTINATO
    run.step()
    assert run.voice.music.position == 1
    assert run.voice.music.heard == 1


def test_the_theme_plays_on_the_title_screen_and_the_ending_is_silent():
    """Three screens and two tunes. **The ending is silence and a count, and
    it stays that way** -- so the shell has no music at all in that state, not
    a stopped one."""
    from spotlight.core.screen import Screen
    from spikes import spike1

    shell = spike1.Shell(Screen())
    assert shell.title_voice.music.tune is tune.THEME
    for _ in range(60):
        shell.frame()
    assert shell.title_voice.music.heard > 0
    assert shell.title_voice.music.position == 60

    import pygame
    shell.key(pygame.K_SPACE)
    assert shell.run.voice.music.tune is tune.OSTINATO
    assert shell.title_voice.music.position == 0, "the theme did not stop"

    shell.state = spike1.ENDED
    heard = shell.title_voice.music.heard
    for _ in range(50):
        shell.frame()
    assert shell.title_voice.music.heard == heard, "the ending made a noise"


def test_a_run_with_no_sound_has_no_music_and_says_so():
    """`sound=False` is the proof that audio decides nothing, so it has to take
    the music with it -- and the report says `None` rather than zero, because
    a zero would read as *the music was never heard*."""
    run = Session(seed=1, metrics=True, sound=False)
    for _ in range(100):
        run.step()
    figures = report.metrics(run)
    assert all(figures[key] is None for key in tune.MUSIC_METRICS)
    assert report.music_lines(run) == []


def test_the_dropout_figures_are_in_every_run_report():
    run = Session(seed=1, metrics=True)
    for _ in range(600):
        run.step()
    figures = report.metrics(run)
    for key in tune.MUSIC_METRICS:
        assert key in figures and figures[key] is not None
    assert any("Music:" in line for line in report.note(run, bot="statue"))


# --- music decides nothing --------------------------------------------------

SEEDS = (1, 2, 3, 4, 5)


@pytest.mark.parametrize("bot", ["listener", "undertaker"])
def test_the_event_log_is_identical_with_music_on_and_off(bot):
    """**Five seeds, two bots, byte for byte.** Music is the lowest thing in
    the arbitration order and it reaches nothing: no rule reads it, no counter
    is reset by it, and the Cleg count it is given is read and not written.

    The repaint figures are in here too, in both counts, because they are the
    round's other standing guarantee and the tester re-takes them after this
    slice expecting no movement at all.
    """
    for seed in SEEDS:
        with_music = _play(bot, seed, music=True)
        without = _play(bot, seed, music=False)
        events = report.results(with_music, bot)["events"]
        assert events == report.results(without, bot)["events"], \
            f"the music changed the run: {bot}, seed {seed}"
        loud, quiet = report.metrics(with_music), report.metrics(without)
        for key, value in loud.items():
            if key in sounds.SOUND_METRICS:
                continue
            assert quiet[key] == value, f"{key} moved when the music stopped"
        assert with_music.voice.music.heard > 0
        assert without.voice.music is None


def _play(bot: str, seed: int, music: bool):
    """One run, with the music taken out of the voice rather than the voice out
    of the run: `sound=False` is a different experiment and is already tested
    in `test_spike_sounds.py`. Here the sonar, the tick and the effects are all
    still sounding and only the tune is gone."""
    run = session_mod.Session(seed=seed, metrics=True)
    if not music:
        run.voice.music = None
    playing = bots.make(bot, seed=seed)
    while run.over is None and run.frame < 9000:
        run.step(playing.intent(run))
    if run.over is None:
        run.finish(session_mod.FRAME_LIMIT)
    return run


# --- one entity, one cost ---------------------------------------------------

def test_exactly_one_module_in_the_build_says_what_a_cleg_costs():
    """**The grep, as a test** (issue #58, and the ruling of 2026-09-11).

    Every budget in the build reads a fly's price from `building.CLEG_COST`.
    The failure this stops is not a wrong number, it is a *second* number: the
    music kept its own copy, the copy went stale when cell-aligned Clegs were
    taken on 2026-09-07, and for five days the music was priced at twice the
    drawing with nothing in the suite able to notice. `building.py` had even
    written down why, quoted from *Nests* -- **"Cleg-equivalents stop being a
    useful currency when the sprite format changes"** -- and then the currency
    changed.

    So: across every module in `spikes/`, exactly one module-level assignment
    names a Cleg's cost, and it is `building`'s.
    """
    found = []
    for path in sorted(pathlib.Path(tune.__file__).parent.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target])
            for target in targets:
                name = getattr(target, "id", "")
                # A name about a fly *and* about what one costs: `CLEG_A` is a
                # sprite bitmap and is not a budget.
                if "CLEG" in name and any(word in name for word in
                                          ("COST", "TSTATE", "CYCLE",
                                           "PRICE", "BUDGET")):
                    found.append((path.name, name))
    assert found == [("building.py", "CLEG_COST")], found
    # And the withdrawn figure is nowhere in the build at all, in any spelling
    # an expression could use.
    for path in sorted(pathlib.Path(tune.__file__).parent.glob("*.py")):
        source = path.read_text()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and node.value == 1654:
                raise AssertionError(f"{path.name} still prices a fly at 1,654")


def test_the_room_has_to_be_fuller_than_any_measured_before_the_music_goes():
    """What the honest price costs the round, asserted as a shape.

    At 830 a Cleg the bass is gone from 21 in one room and the last of the
    music from 35, where at the withdrawn 1,654 those were 11 and 18. Over the
    whole sample this round has used -- 172,011 frames, seven bots, five seeds,
    counting flies in the room the player is actually in -- the bass goes on
    0.24% of frames and **the music never goes at all**, because the busiest
    room anybody has seen held twenty-five.

    **The twenty-five is an observation and not a bound**, which is the lesson
    `building.FIXTURE_COST` learned the hard way: a sample cannot bound a worst
    case, and a wider sweep may well find a fuller room. So this asserts the
    shape -- rare, and rarer for the motif than the bass -- rather than the
    fraction, and it does not assert that the music never goes, because that is
    not something a run of the suite could know. The bound is `WORST_CLEGS`,
    and at the bound the music is silent; that is the test above.
    """
    #: The busiest room seen over the sample, recorded so the arithmetic below
    #: can be read against it. Not a bound. Not asserted about the game.
    MEASURED_PEAK = 25

    def gone_from(index):
        """The fewest Clegs at which this note affords nothing."""
        return next(n for n in range(tune.WORST_CLEGS + 2)
                    if not tune.half_cycles(tune.leftover(n),
                                            tune.PERIODS[index]))

    bass, motif = gone_from(tune.A2), gone_from(tune.A4)
    assert (bass, motif) == (21, 35)
    # The bass still goes in a room the sample actually reached, so the
    # dropout is not decorative -- it just fires rarely.
    assert bass < MEASURED_PEAK
    # The whole tune going needs a room fuller than anything measured.
    assert motif > MEASURED_PEAK
    # And the ordering is the one *Music and Sound* leans on: the floor goes
    # first and the voice last, whatever a fly costs.
    assert bass < motif


# --- the module stays portable ----------------------------------------------

def test_the_tune_module_imports_no_host_and_has_no_floats_in_it():
    """`test_portability.py` governs this for every module that is not named
    `spike*`, and this says it again about the one module the issue names --
    because *the port inherits data rather than a performance* is the whole
    reason this file exists, and a float in it would be a figure the assembler
    cannot take."""
    source = pathlib.Path(tune.__file__).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            assert not isinstance(node.value, float)
    assert "pygame" not in source.replace("no pygame", "")
    assert "numpy" not in source.replace("no numpy", "")


# --- helpers ----------------------------------------------------------------

def _levels(block: bytes) -> list:
    import struct
    return list(struct.unpack(f"<{len(block) // 2}h", block))


def _flips(block: bytes, was: int) -> list:
    """Sample indices where the bit changed, given where it was before.

    `was` is the level the frame started from, which matters: the engine flips
    *first* and then holds, so a frame that sounds at all flips at index zero
    and a frame that does not never flips.
    """
    levels = _levels(block)
    out = []
    last = was * spike_sound.AMPLITUDE
    for i, level in enumerate(levels):
        if level != last:
            out.append(i)
            last = level
    return out
