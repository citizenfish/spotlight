"""One speaker: the table, the arbitration, and the two voices that moved house.

Issue #54. Three kinds of test are in here and they are worth telling apart:

* **The table is the note's**, so these tests check that what is built matches
  *Music and Sound#The sound table* and *Art Direction#8. The moments* rather
  than checking that it sounds nice. A pitch is a design decision and belongs
  to the vault; that the build plays the pitch the vault names is this file's.
* **The arbitration is a ruling**, and every clause of it is pinned -- most of
  all the three the ruling left to slice F to build deliberately, because a
  boundary settled by accident is a boundary nobody can argue with later.
* **The two built voices did not change.** They changed owner. Their bytes are
  pinned against the commit before this slice, because "we only moved it" is
  the claim that is always made and is not always true.
"""

import hashlib

import pytest

from spikes import buzz, moments as M, session as session_mod, sounds
from spikes.session import Session


# --- the two voices moved house and did not change --------------------------
#
# `click_wave` and `tick_wave` are tuned by ear and are quoted in the vault as
# figures the sound table was built *around*. `interval_for` is the sonar's
# whole meaning: rate is distance. All three were carried onto the one speaker
# in this slice, so all three are pinned to what they were at f2c477e, the
# commit before it.

#: sha256 of the built waves at f2c477e, mono and stereo. A hash rather than a
#: golden file: the bytes are not readable and the only question anybody has
#: about them is whether they are the same ones.
CLICK_SHA = ("cda62048077656b4454e3684f50c2e707c499b111a9234c90b48aae7fdcaabb5",
             "6efd6cbbec0729c0fdbaa606338740f36e644bb40fa82c02549423388934bce2")
TICK_SHA = ("a8d16cb8a408d9fc395ce051c0d68311e846bcae2834c24107397d01ca761792",
            "fd7ff6e411580ea24bbed38a95f06b04de30d0526aa4d952ea307149bb1d40e7")

#: `buzz.interval_for` at every distance from 0 to 12, at f2c477e: 8 frames on
#: contact, 29 halfway in, 46 at the edge of hearing, silence at the reach.
INTERVALS = (8, 11, 15, 18, 22, 25, 29, 32, 36, 39, 43, 46, 0)


def test_the_click_and_the_tick_are_byte_for_byte_what_they_were():
    from spikes import spike_buzz

    for stereo in (False, True):
        assert hashlib.sha256(
            spike_buzz.click_wave(stereo=stereo)).hexdigest() \
            == CLICK_SHA[stereo], "the sonar's click was retuned"
        assert hashlib.sha256(
            spike_buzz.tick_wave(stereo=stereo)).hexdigest() \
            == TICK_SHA[stereo], "the body's tick was retuned"


def test_every_sonar_rate_is_what_it_was():
    """46 frames at the edge, 29 halfway, 8 on contact, over a reach of 12."""
    assert tuple(buzz.interval_for(d) for d in range(13)) == INTERVALS
    assert buzz.REACH == 12
    assert buzz.interval_for(11) == 46 and buzz.interval_for(6) == 29
    assert buzz.interval_for(0) == 8


def test_there_is_only_one_speaker_class_left():
    """The two audio paths became one, which was half the point of the slice.

    `spike_buzz.Speaker` played the click and the tick straight from the
    session while the fourteen effects had no voice at all. If it comes back,
    the arbitration order has two implementations again and only one of them is
    the design's.
    """
    from spikes import spike_buzz

    assert not hasattr(spike_buzz, "Speaker"), \
        "a second audio path came back"


# --- the table is the note's -------------------------------------------------

#: Straight out of *Music and Sound#The sound table*: how long each effect
#: lasts, in frames. Retyped here rather than derived, so that a change to the
#: segments has to be a deliberate change to a number a listener chose.
TABLE_FRAMES = {
    M.SFX_FREED: 12, M.SFX_DELIVERED: 26, M.SFX_BITE: 5,
    M.SFX_WORKER_DIED: 18, M.SFX_PLAYER_DIED: 40, M.SFX_TORCH_OUT: 24,
    M.SFX_DOOR: 2, M.SFX_SPRAY: 6, M.SFX_SPRAY_KILL: 3,
    M.SFX_NEST_TURNED: 24, M.SFX_HATCHED: 30, M.SFX_GAME_OVER: 66,
    M.SFX_ALL_OUT: 50, M.SFX_PICKUP: 8,
}


def test_all_fourteen_are_here_and_no_fifteenth():
    assert sorted(sounds.EFFECTS) == list(range(14))
    assert sorted(sounds.EFFECTS) == [M.MOMENTS[n].sound for n in M.MOMENTS]


def test_every_effect_lasts_what_the_table_says():
    for sound, frames in TABLE_FRAMES.items():
        assert sounds.EFFECTS[sound].frames == frames, \
            f"{M.SOUND_NAMES[sound]} is not the length the note gives it"


def test_the_priorities_are_art_directions_and_are_not_copied():
    """Two tables, one set of priorities. *Art Direction* wins where they
    disagree, so the test is that they cannot."""
    for moment in M.MOMENTS.values():
        assert sounds.EFFECTS[moment.sound].priority == moment.priority, \
            f"{moment.name} has two different priorities"
    assert {s: e.priority for s, e in sounds.EFFECTS.items()} == {
        M.SFX_FREED: 0, M.SFX_DELIVERED: 0, M.SFX_BITE: 0,
        M.SFX_WORKER_DIED: 1, M.SFX_PLAYER_DIED: 1, M.SFX_TORCH_OUT: 0,
        M.SFX_DOOR: 0, M.SFX_SPRAY: 0, M.SFX_SPRAY_KILL: 0,
        M.SFX_NEST_TURNED: 1, M.SFX_HATCHED: 0, M.SFX_GAME_OVER: 1,
        M.SFX_ALL_OUT: 1, M.SFX_PICKUP: 0,
    }


def test_a_period_is_t_states_and_a_duty_is_a_division():
    """The two integers a note is, and the arithmetic the port does on them."""
    assert sounds.TSTATES == 3_500_000
    assert sounds.period_of(1000) == 3500
    # 1:2 is a square, 1:4 a quarter high, and it is the same loop either way.
    assert sounds.high_of(3500, 2) == 1750
    assert sounds.high_of(3500, 4) == 875
    assert sounds.high_of(3500, 8) == 437


def test_the_pitches_the_note_names_are_the_pitches_that_play():
    """Every named pitch, back out of the built table, within the rounding.

    A period is whole T-states, so a pitch comes back within a fraction of a
    percent rather than exactly. Nothing in the table is above 2kHz, where the
    grid is finer than seven cents, so this is the whole of the error.
    """
    named = {
        M.SFX_FREED: (523, 785),
        M.SFX_DELIVERED: (523, 658, 785, 1048),
        M.SFX_BITE: (900, 260),
        M.SFX_PICKUP: (880, 1313),
        M.SFX_DOOR: (233, 175),
        M.SFX_ALL_OUT: (440, 658, 880, 785, 880),
        M.SFX_GAME_OVER: (330, 247, 196, 110, 98),
    }
    for sound, pitches in named.items():
        effect = sounds.EFFECTS[sound]
        ends = []
        for segment in effect.segments:
            ends.append(segment.start)
            if segment.end != segment.start:
                ends.append(segment.end)
        assert tuple(ends) == pitches, M.SOUND_NAMES[sound]
        for hz in pitches:
            played = sounds.TSTATES // sounds.period_of(hz)
            assert abs(played - hz) <= 1, f"{hz}Hz came out at {played}Hz"


def test_good_news_rises_and_bad_news_falls():
    """The corollary the table is built on, and it is load-bearing.

    Two unpitched clicking voices mean every effect has to be a *shape*, and
    the shape carries the news. `SFX_HATCHED` is the deliberate exception: it
    rises because it is a thing being born, and it rises as a rasp, which is
    the only way this voice has of saying that a rising line is not good news.
    """
    def ends(sound):
        segments = sounds.EFFECTS[sound].segments
        return segments[0].start, segments[-1].end

    for sound in (M.SFX_FREED, M.SFX_DELIVERED, M.SFX_PICKUP, M.SFX_ALL_OUT):
        first, last = ends(sound)
        assert last > first, f"{M.SOUND_NAMES[sound]} does not rise"
    for sound in (M.SFX_BITE, M.SFX_WORKER_DIED, M.SFX_PLAYER_DIED,
                  M.SFX_TORCH_OUT, M.SFX_GAME_OVER, M.SFX_DOOR):
        first, last = ends(sound)
        assert last < first, f"{M.SOUND_NAMES[sound]} does not fall"
    first, last = ends(M.SFX_HATCHED)
    assert last > first, "the one thing that is born does not rise"


def test_only_the_clegs_rasp():
    """A rasp is a jittered delay constant and it means *Cleg*.

    Nothing else in the game has an unstable pitch, which is what makes the
    rasp mean anything at all. The two deaths rasp because a Cleg is in them;
    the torch's dying rattle is the one non-Cleg rasp and it is a mechanism
    failing rather than a pitch.
    """
    rasped = {sound for sound, effect in sounds.EFFECTS.items()
              if any(s.jitter for s in effect.segments)}
    assert rasped == {M.SFX_NEST_TURNED, M.SFX_HATCHED, M.SFX_WORKER_DIED,
                      M.SFX_PLAYER_DIED, M.SFX_TORCH_OUT}
    for sound in (M.SFX_FREED, M.SFX_DELIVERED, M.SFX_BITE, M.SFX_PICKUP,
                  M.SFX_ALL_OUT, M.SFX_DOOR, M.SFX_GAME_OVER):
        assert sound not in rasped, f"{M.SOUND_NAMES[sound]} has a wobble"


def test_a_glide_is_linear_in_the_period_and_not_in_the_pitch():
    """**Not a bug and not to be fixed.**

    A Z80 decrements a delay constant; it does not compute a frequency. The
    bite's chirp steps the period evenly from 900Hz to 260Hz, which sags
    towards the low end -- the midpoint is well below the 580Hz a linear glide
    in pitch would pass through, and that is what the machine sounds like.
    """
    bite = sounds.EFFECTS[M.SFX_BITE]
    periods = [bite.note(i).period for i in range(bite.frames)]
    steps = [b - a for a, b in zip(periods, periods[1:])]
    # Even to within the integer division, which is the same rounding a
    # precomputed table on the target would carry.
    assert max(steps) - min(steps) <= 1, "the glide is not even in the period"
    assert periods[0] == sounds.period_of(900)
    assert periods[-1] == sounds.period_of(260)
    middle = sounds.TSTATES // periods[len(periods) // 2]
    assert middle < 580, "the glide was 'fixed' to be even in pitch"


def test_the_noise_is_a_named_lfsr_and_not_the_games_random_stream():
    """Both machines have to make the same hiss, so the tap is written down.

    And it is deliberately not `sources.xorshift16`: that chain is where every
    fly's temperament comes from, and a speaker drawing on it would make audio
    a thing that changes the run.
    """
    assert sounds.LFSR_TAPS == 0xB400
    state = sounds.LFSR_SEED
    seen = set()
    for _ in range(5000):
        state = sounds.lfsr_next(state)
        assert state, "the shift register fell to zero"
        seen.add(state)
    assert len(seen) > 4000, "the sequence repeats far too soon to be noise"
    spray = sounds.EFFECTS[M.SFX_SPRAY]
    assert spray.note(0).kind == sounds.NOISE
    assert spray.note(0).period == sounds.SPRAY_STEP == 70


def test_a_rasp_stays_inside_its_swing():
    """The jitter is a pair of delay constants, so it cannot run away."""
    nest = sounds.EFFECTS[M.SFX_NEST_TURNED]
    note = nest.note(0)
    assert note.kind == sounds.RASP
    assert note.period == sounds.period_of(105 + 18)
    assert note.period_hi == sounds.period_of(105 - 18)
    state = sounds.LFSR_SEED
    for _ in range(500):
        state = sounds.lfsr_next(state)
        period = sounds.jittered(state, note.period, note.period_hi)
        assert note.period <= period <= note.period_hi


def test_every_delay_constant_fits_in_a_register_pair():
    """The port plays these from a 16-bit counter, so they have to fit in one.

    The longest is the 62Hz tail of the player's death at 56,451 T-states,
    which is comfortably inside 65,535 -- but it is nine tenths of the way
    there, so a fifteenth row an octave lower would not fit and would need a
    different loop. Worth failing over now rather than discovering in Z80.
    """
    for sound, effect in sounds.EFFECTS.items():
        for i in range(effect.frames):
            note = effect.note(i)
            assert note.period <= 0xFFFF and note.period_hi <= 0xFFFF, \
                f"{M.SOUND_NAMES[sound]} needs more than 16 bits of delay"


def test_every_frame_of_every_effect_says_something():
    """No effect has a silent frame in it: a length is a length."""
    for sound, effect in sounds.EFFECTS.items():
        for i in range(effect.frames):
            note = effect.note(i)
            assert note.kind != sounds.SILENT, \
                f"{M.SOUND_NAMES[sound]} is silent on frame {i}"
            if note.kind != sounds.NOISE:
                assert note.period > 0 and note.high > 0
        assert effect.note(effect.frames).kind == sounds.SILENT, \
            "walking off the end of an effect should be silence, not an error"


# --- the arbitration ---------------------------------------------------------

def _voice_playing(sound=M.SFX_GAME_OVER):
    """A voice with an effect running and frames still to come."""
    voice = sounds.Voice()
    voice.update(False, False, [(sound, sounds.EFFECTS[sound].priority)])
    assert voice.kind == sounds.EFFECT
    return voice


def test_a_click_alone_sounds():
    voice = sounds.Voice()
    assert voice.update(True, False) == sounds.CLICK
    assert voice.clicks.sounded == 1 and voice.clicks.dropped == 0


def test_the_sonar_beats_the_body_tick():
    """The order's first clause, and the one that predates everything else."""
    voice = sounds.Voice()
    assert voice.update(True, True) == sounds.CLICK
    assert voice.ticks.dropped == 1 and voice.ticks.sounded == 0


def test_a_click_and_an_effect_on_the_same_frame_the_click_wins():
    """**The boundary the ruling did not reach, built deliberately.**

    The effect has not started, so it does not yet own anything, and the click
    takes the frame. The effect is *not queued*: it never starts, and the next
    frame is silent rather than the effect beginning late.

    This is the designer's reading rather than the user's words, and it is the
    only one that keeps the sonar's counter regular. If it later turns out to
    swallow a bite the player needed to hear, this test and the paragraph in
    `sounds` are the sentence to argue with.
    """
    voice = sounds.Voice()
    assert voice.update(True, False, [(M.SFX_BITE, 0)]) == sounds.CLICK
    assert voice.effects_dropped == 1 and voice.effects_sounded == 0
    assert voice.update(False, False) == sounds.NOTHING, \
        "the effect was queued after all"


def test_a_tick_and_an_effect_on_the_same_frame_the_tick_wins():
    """The same, for the body's tick. **This is the extension**, flagged as
    one: the ruling was made about the click and the tick is the same shape of
    thing -- one frame, unpitched, a rate rather than a shape."""
    voice = sounds.Voice()
    assert voice.update(False, True, [(M.SFX_BITE, 0)]) == sounds.TICK
    assert voice.effects_dropped == 1
    assert voice.update(False, False) == sounds.NOTHING


#: Every sound in the table that is short enough to be inviolable, which is
#: every sound the grace window promises to leave alone. `SFX_WORKER_DIED` is
#: the longest of them **and is where the number 18 comes from**.
SHORT_SOUNDS = tuple(sound for sound, effect in sounds.EFFECTS.items()
                     if effect.frames <= sounds.GRACE_FRAMES)


def test_the_window_is_the_length_of_the_workers_death():
    """**Eighteen is read off the table, not tuned**, and this is the line that
    keeps it that way.

    *When the sonar lands inside an effect* set the window at the length of the
    longest sound that is a single event rather than a shape with room in it --
    the worker's death, one of the two beats *Nests* says the body-and-nest
    mechanic rests on. If somebody shortens that sound, this fails and the
    window is re-argued rather than silently left behind.
    """
    assert sounds.GRACE_FRAMES == sounds.EFFECTS[M.SFX_WORKER_DIED].frames
    assert M.SFX_WORKER_DIED in SHORT_SOUNDS
    # ...and the six the acceptance criteria name by hand, so that a table
    # change cannot make the promise true by emptying the list.
    for sound in (M.SFX_BITE, M.SFX_FREED, M.SFX_WORKER_DIED, M.SFX_DOOR,
                  M.SFX_SPRAY, M.SFX_PICKUP):
        assert sound in SHORT_SOUNDS


@pytest.mark.parametrize("sound", SHORT_SOUNDS)
def test_a_sound_that_is_one_event_is_inviolable(sound):
    """**The half of the ruling that did not change.**

    A sound of `GRACE_FRAMES` or fewer owns the voice for every frame it has:
    a bite, a freeing, a worker's death, a door, a spray, a pickup. In 57
    minutes of measured play not one of them lost a frame, and this is the
    test that keeps it so. The click is dropped rather than queued, and
    nothing anywhere near the sonar's counter is touched.
    """
    voice = _voice_playing(sound)
    frames = sounds.EFFECTS[sound].frames
    played = [voice.kind]
    for _ in range(1, frames):
        # A click on every single frame of it, which is worse than the game can
        # do: the fastest the sonar goes is one in eight.
        played.append(voice.update(True, False))
    assert played == [sounds.EFFECT] * frames
    assert voice.clicks.dropped == frames - 1 and voice.clicks.sounded == 0
    assert voice.frames_lost == 0, "a single event was interrupted"
    # ...and the frame after it ends, the voice is free again.
    assert voice.update(True, False) == sounds.CLICK


def test_the_grace_window_is_pinned_in_both_directions():
    """**The boundary, and the whole of issue #57 in six lines.**

    Frame 17 of an effect is still inside the window and a click due there is
    dropped; frame 18 is outside it and the same click is heard. Both
    directions, because a window pinned on one side is a window that can drift
    on the other.
    """
    for position, expected in ((sounds.GRACE_FRAMES - 1, sounds.EFFECT),
                               (sounds.GRACE_FRAMES, sounds.CLICK)):
        voice = _voice_playing(M.SFX_HATCHED)          # 30 frames, priority 0
        for _ in range(position - 1):
            voice.update(False, False)
        assert voice.position == position, "the test walked to the wrong frame"
        assert voice.update(True, False) == expected
    # And the tick is treated exactly as the click, which is this build's
    # extension of the ruling rather than the ruling's own words.
    voice = _voice_playing(M.SFX_HATCHED)
    for _ in range(sounds.GRACE_FRAMES - 1):
        voice.update(False, False)
    assert voice.update(False, True) == sounds.TICK


def test_a_punctured_effect_is_not_abandoned_and_not_restarted():
    """It loses the frame the click takes and carries on. **Not truncated.**

    The alternative that was measured and rejected -- cap the ownership and
    abandon the rest -- gives the same starvation figures and deletes 1,383
    frames of sound. An effect here is a shape: cut `SFX_PLAYER_DIED` at frame
    18 and what is left is a falling tone that stops, which is the beginning of
    four other sounds. So the hole is a hole, and the sound ends exactly where
    it always would have.
    """
    voice = _voice_playing(M.SFX_PLAYER_DIED)          # 40 frames
    frames = sounds.EFFECTS[M.SFX_PLAYER_DIED].frames
    heard = {}
    for frame in range(1, frames):
        # A click every eight frames: the sonar at contact, which is when this
        # actually happens.
        kind = voice.update(frame % 8 == 0, False)
        if kind == sounds.EFFECT:
            heard[frame] = voice.index
    # The sound still ends on the frame it would have ended on...
    assert voice.update(False, False) == sounds.NOTHING
    assert voice.sound == M.SFX_PLAYER_DIED, "the effect was replaced"
    # ...every frame it was heard on is the frame of the sound it should have
    # been, in order, with holes where the clicks were...
    assert list(heard.values()) == sorted(heard.values())
    assert all(frame == index for frame, index in heard.items())
    # ...and the holes are only ever past the window.
    holes = sorted(set(range(frames)) - set(heard.values()) - {0})
    assert holes == [24, 32] and voice.frames_lost == 2
    assert min(holes) >= sounds.GRACE_FRAMES


def test_the_frame_after_a_hole_tells_the_host_to_pick_the_sound_up():
    """`resumed` exists for the host and the port does not need it.

    pygame is handed a whole effect at once, so a click that stops the channel
    has to be followed by the rest of the sound; a Z80 reads the next note off
    the table and notices nothing. See `spike_sound.Speaker`.
    """
    voice = _voice_playing(M.SFX_HATCHED)
    for _ in range(sounds.GRACE_FRAMES - 1):
        assert not voice.resumed
        voice.update(False, False)
    assert voice.update(True, False) == sounds.CLICK
    assert voice.update(False, False) == sounds.EFFECT
    assert voice.resumed and not voice.started
    assert voice.index == sounds.GRACE_FRAMES + 1
    voice.update(False, False)
    assert not voice.resumed, "the host was told to start the sound twice"


def test_a_priority_one_effect_still_pre_empts_past_the_window():
    """The priority rule predates this and is untouched by it."""
    voice = _voice_playing(M.SFX_HATCHED)              # priority 0, 30 frames
    for _ in range(sounds.GRACE_FRAMES + 4):
        voice.update(True, False)                      # punching holes in it
    assert voice.frames_lost, "the test never got past the window"
    assert voice.update(False, False,
                        [(M.SFX_WORKER_DIED, 1)]) == sounds.EFFECT
    assert voice.sound == M.SFX_WORKER_DIED and voice.index == 0
    assert voice.effects_cut == 1


def test_a_dropped_click_does_not_touch_the_sonars_counter():
    """**Dropped means dropped, not deferred.**

    The sonar's rate is the only thing carrying distance, so a counter that
    restarted when a click was lost would make the rate mean something else.
    The counter is run here exactly as the session runs it, with an effect
    hogging the voice throughout, and the frames it comes due on are compared
    with the same counter left alone.
    """
    alone = buzz.Sonar()
    due_alone = [alone.update(3) for _ in range(200)]

    drowned = buzz.Sonar()
    voice = sounds.Voice()
    due_drowned = []
    for frame in range(200):
        wanted = drowned.update(3)
        due_drowned.append(wanted)
        # A fresh game-over on the frame it ends, so the voice is never free.
        wants = [(M.SFX_GAME_OVER, 1)] if frame % 66 == 0 else []
        voice.update(wanted, False, wants)
    assert due_drowned == due_alone, "a dropped click moved the sonar's counter"
    assert voice.clicks.dropped == sum(due_alone) - voice.clicks.sounded
    # The grace window means some of those clicks were *heard* inside the
    # effect, which is the new path through the arbiter: it must not touch the
    # counter either, and this is what makes the run above exercise it.
    assert voice.clicks.sounded and voice.frames_lost


def test_the_next_click_lands_exactly_where_it_would_have():
    """The other half of the same rule, stated as the player hears it."""
    sonar, voice = buzz.Sonar(), sounds.Voice()
    heard = []
    for frame in range(60):
        wanted = sonar.update(0)             # contact: one click in eight
        wants = [(M.SFX_BITE, 0)] if frame == 3 else []
        if voice.update(wanted, False, wants) == sounds.CLICK:
            heard.append(frame)
    # Clicks on frames 7, 15, 23 ... and the bite on frame 3 runs 3 to 7, so
    # the one at 7 is dropped and the one at 15 arrives on time regardless.
    assert 7 not in heard, "the bite did not own the voice"
    assert heard == [15, 23, 31, 39, 47, 55]


def test_priority_one_cuts_priority_zero():
    """Ownership is against the clicks, not against a louder piece of news."""
    voice = _voice_playing(M.SFX_TORCH_OUT)         # priority 0, 24 frames
    voice.update(False, False)
    assert voice.update(False, False, [(M.SFX_WORKER_DIED, 1)]) == sounds.EFFECT
    assert voice.sound == M.SFX_WORKER_DIED
    assert voice.index == 0, "the interrupting effect did not start at its start"
    assert voice.effects_cut == 1
    assert voice.left == sounds.EFFECTS[M.SFX_WORKER_DIED].frames - 1


def test_priority_zero_during_anything_is_dropped():
    for running in (M.SFX_TORCH_OUT, M.SFX_GAME_OVER):
        voice = _voice_playing(running)
        voice.update(False, False, [(M.SFX_BITE, 0)])
        assert voice.sound == running, "a quiet piece of news cut in"
        assert voice.effects_dropped == 1 and voice.effects_cut == 0


def test_priority_one_during_priority_one_is_dropped_first_come():
    voice = _voice_playing(M.SFX_GAME_OVER)         # priority 1
    voice.update(False, False, [(M.SFX_PLAYER_DIED, 1)])
    assert voice.sound == M.SFX_GAME_OVER, "first come did not keep the voice"
    assert voice.effects_dropped == 1 and voice.effects_cut == 0


def test_two_effects_on_one_frame_settle_between_themselves():
    """Raised together, the louder one wins whichever order they arrive in."""
    for order in ([(M.SFX_BITE, 0), (M.SFX_WORKER_DIED, 1)],
                  [(M.SFX_WORKER_DIED, 1), (M.SFX_BITE, 0)]):
        voice = sounds.Voice()
        assert voice.update(False, False, order) == sounds.EFFECT
        assert voice.sound == M.SFX_WORKER_DIED
        assert voice.index == 0


def test_nothing_is_ever_queued():
    """A loser is not heard, and the state is one effect and its frames left."""
    voice = sounds.Voice()
    voice.update(False, False, [(M.SFX_BITE, 0), (M.SFX_DOOR, 0),
                                (M.SFX_PICKUP, 0)])
    for _ in range(sounds.EFFECTS[M.SFX_BITE].frames - 1):
        voice.update(False, False)
    assert voice.update(False, False) == sounds.NOTHING, \
        "something was waiting its turn"
    assert voice.effects_dropped == 2


def test_an_effect_plays_its_frames_in_order_and_then_stops():
    voice = sounds.Voice()
    voice.update(False, False, [(M.SFX_DELIVERED, 0)])
    seen = [voice.index]
    for _ in range(sounds.EFFECTS[M.SFX_DELIVERED].frames - 1):
        voice.update(False, False)
        seen.append(voice.index)
    assert seen == list(range(sounds.EFFECTS[M.SFX_DELIVERED].frames))
    assert voice.update(False, False) == sounds.NOTHING


def test_the_quiet_measured_is_silence_the_sonar_did_not_ask_for():
    """Not the gap between clicks: at the edge of hearing that is 46 frames by
    design and means nothing. The figure is from a dropped click to the next
    one heard, which is what the ruling asked to be measured."""
    sonar, voice = buzz.Sonar(), sounds.Voice()
    for frame in range(200):
        wanted = sonar.update(11)                 # the edge: 46 frames apart
        voice.update(wanted, False, [])
    assert voice.clicks.sounded == 4 and voice.clicks.dropped == 0
    assert voice.clicks.quiet == 0, "a rate was reported as a starvation"


def test_a_run_that_ends_while_the_sonar_is_drowned_out_still_counts_it():
    """The worst case happens at the end of a run, which is exactly when a
    figure that only closed on a heard click would forgive it."""
    voice = sounds.Voice()
    # The worker's death, because it is inviolable end to end: a longer sound
    # would let a click through at frame 18 and stop the silence, which is the
    # grace window working rather than the measurement failing.
    voice.update(False, False, [(M.SFX_WORKER_DIED, 1)])
    frames = sounds.EFFECTS[M.SFX_WORKER_DIED].frames
    for _ in range(frames - 1):
        voice.update(True, False)
    assert voice.clicks.quiet == frames - 1
    assert voice.starved(), "seventeen frames of silence went unreported"


# --- one speaker, over a real run -------------------------------------------

def test_at_most_one_thing_sounds_on_any_frame_of_a_long_run():
    """One speaker, and now it is a value rather than a promise."""
    run = Session(seed=1, lives=99)
    seen = set()
    for _ in range(6000):
        run.step()
        if run.over is not None:
            break
        seen.add(run.voice.kind)
        assert not (run.click and run.tick), "two voices on one speaker"
        if run.voice.kind == sounds.EFFECT:
            assert not run.click and not run.tick
    assert {sounds.CLICK, sounds.EFFECT} <= seen, \
        "the run never exercised both a click and an effect"


def test_the_effects_are_heard_in_a_real_run():
    """The seam slice D left open is closed: something reads a sound id."""
    run = Session(seed=1, lives=99)
    played = set()
    for _ in range(9000):
        run.step()
        if run.over is not None:
            break
        if run.voice.kind == sounds.EFFECT and run.voice.started:
            played.add(run.voice.sound)
    assert played, "a whole run went by without an effect being heard"
    assert M.SFX_BITE in played or M.SFX_DOOR in played


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_run_never_plays_a_frame_of_an_effect_out_of_order(seed):
    """Every effect heard is heard from its start, in order, and never twice.

    A cut effect stops part way -- that is the pre-emption rule -- and nothing
    is ever queued. **A punctured one skips the frame the click took** (issue
    #57) and goes on from the next, so a gap in what is heard is allowed and a
    repeat or a step backwards is not: playing the same frame twice would mean
    the sonar had lengthened a sound instead of holing it.
    """
    from spikes import bots

    # A bot rather than an idle player, because a still player hears almost
    # nothing: the idle version of this test ran 4,000 frames without a single
    # hole in it and would have passed whatever the arbiter did.
    run = Session(seed=seed, lives=99)
    player = bots.make("wanderer", seed=seed)
    last = None
    holes = 0
    for _ in range(4000):
        run.step(player.intent(run))
        if run.over is not None:
            break
        voice = run.voice
        if voice.kind != sounds.EFFECT:
            continue
        if voice.started:
            assert voice.index == 0
            last = -1
        else:
            assert last is not None and voice.index > last, \
                "a frame of an effect was heard twice"
            if voice.index > last + 1:
                # **Every hole in a real run is where the rule says it may be**:
                # in a sound long enough to have a middle, past its eighteenth
                # frame. A bite, a freeing, a worker's death, a door, a spray
                # and a pickup are all shorter than the window and none of them
                # can appear here.
                assert sounds.EFFECTS[voice.sound].frames > sounds.GRACE_FRAMES
                assert last + 1 >= sounds.GRACE_FRAMES
            holes += voice.index - last - 1
            assert voice.resumed == (voice.index > last + 1)
        last = voice.index
    assert holes == run.voice.frames_lost


# --- the effect clock belongs to the interrupt -------------------------------

def test_a_frame_the_game_did_not_step_still_ages_the_sound():
    """**The defect, in the small** (issue #57). See `Voice.audio_frame`.

    The clock that says how much of an effect is left is the sound player's,
    and the sound player is the 50Hz interrupt. A frame the game did not step
    is still a frame of sound, so it is still twenty milliseconds of the
    effect, and the arbiter must not go on guarding a sound the speaker has
    already finished.
    """
    voice = _voice_playing(M.SFX_PLAYER_DIED)          # 40 frames
    frames = sounds.EFFECTS[M.SFX_PLAYER_DIED].frames
    for held in range(1, frames):
        assert voice.audio_frame() == sounds.EFFECT
        assert voice.index == held
    # The whole sound has now played out in held frames, so the voice is free
    # and the very next click is heard rather than dropped.
    assert voice.audio_frame() == sounds.NOTHING
    assert voice.update(True, False) == sounds.CLICK
    assert voice.clicks.dropped == 0


def test_held_frames_do_not_count_as_clicks_lost():
    """Nothing is asked for in a frame the game did not step, so nothing can be
    dropped in one: the sonar's counter is inside the session and did not
    advance either. A held frame ages the sound and says nothing else."""
    voice = _voice_playing(M.SFX_GAME_OVER)
    for _ in range(25):
        voice.audio_frame()
    assert voice.clicks.dropped == 0 and voice.clicks.quiet == 0
    assert voice.ticks.dropped == 0
    assert voice.frames_lost == 0, "a held frame was counted as a hole"


def test_the_starvation_figures_are_in_every_run_report():
    from spikes import report

    run = Session(seed=1, metrics=True)
    for _ in range(400):
        run.step()
    figures = report.metrics(run)
    for key in sounds.SOUND_METRICS:
        assert key in figures and figures[key] is not None
    assert any("Speaker:" in line for line in report.note(run, bot="statue"))


def test_a_run_with_no_voice_still_has_the_columns():
    """A run played without a speaker reports `None`, not zero: a zero would
    read as *nothing was ever dropped*, which is a different claim."""
    from spikes import report

    run = Session(seed=1, metrics=True, sound=False)
    for _ in range(200):
        run.step()
    figures = report.metrics(run)
    assert all(figures[key] is None for key in sounds.SOUND_METRICS)
    assert not any("Speaker:" in line for line in report.note(run))


# --- audio decides nothing ---------------------------------------------------

SEEDS = (1, 2, 3, 4, 5)


@pytest.mark.parametrize("bot", ["listener", "undertaker"])
def test_the_event_log_is_identical_with_sound_on_and_off(bot):
    """**The strongest form the promise takes.** Five seeds, two bots.

    A speaker that changed a run would be the worst kind of bug in this
    project, because every number in every playtest note comes from a headless
    run and the whole round is measured on the logs not moving. The arbiter
    reads nothing, writes nothing back, and never touches the two counters --
    and this is how that stops being an argument and becomes a fact.

    The repaint figures are in here too, deliberately: they are the round's
    other standing guarantee, and a sound that cost a cell repaint would be
    caught here rather than in a tester's table a week later.
    """
    from spikes import bots, report, spike_driver

    for seed in SEEDS:
        loud = spike_driver.drive(bots.make(bot, seed=seed), seed=seed)
        quiet = spike_driver.drive(bots.make(bot, seed=seed), seed=seed)
        quiet_run = session_mod.Session(seed=seed, metrics=True, sound=False)
        # The third run is the one that matters: no voice at all.
        bot_quiet = bots.make(bot, seed=seed)
        while quiet_run.over is None and quiet_run.frame < 9000:
            quiet_run.step(bot_quiet.intent(quiet_run))
        if quiet_run.over is None:
            quiet_run.finish(session_mod.FRAME_LIMIT)

        events = report.results(loud, bot)["events"]
        assert events == report.results(quiet, bot)["events"]
        assert events == report.results(quiet_run, bot)["events"], \
            f"the speaker changed the run: {bot}, seed {seed}"
        for key, value in report.metrics(loud).items():
            if key in sounds.SOUND_METRICS:
                continue
            assert report.metrics(quiet_run)[key] == value, \
                f"{key} moved when the speaker was switched off"


@pytest.mark.parametrize("bot", ["listener", "undertaker", "wanderer"])
def test_a_click_is_only_ever_lost_to_an_effect_that_owns_the_voice(bot):
    """The invariant behind every starvation figure in the report.

    A click is dropped for exactly one reason -- an effect had already started
    and owns the voice for its length -- and never because the arbiter mislaid
    it. If a drop ever happened on a frame where nothing was sounding, the
    figures below would be measuring a bug rather than the design.
    """
    from spikes import bots

    for seed in SEEDS:
        run = session_mod.Session(seed=seed)
        player = bots.make(bot, seed=seed)
        dropped = 0
        while run.over is None and run.frame < 4000:
            before = run.voice.clicks.dropped
            run.step(player.intent(run))
            if run.voice.clicks.dropped > before:
                dropped += 1
                assert run.voice.kind == sounds.EFFECT, \
                    "a click was lost to nothing at all"
        assert dropped or run.frame < 4000


#: **The finding, measured rather than assumed**, and then the ruling it forced.
#: Slice F measured the first arbitration over seven bots and five seeds --
#: 172,011 frames, 57 minutes -- and found 571 of 7,562 clicks dropped (7.6%),
#: the sonar quiet for **87 frames, 1.74 seconds**, and **six clicks lost in a
#: row at contact**: a motionless player with a fly on them and nothing in the
#: second before the bite. *Questions#Prompt 3* says a bite is never a
#: surprise, so that was the figure the ruling turned on and not the 87.
#:
#: **Re-measured over the same runs with the grace window** (issue #57): 409
#: dropped (5.4%), worst silence 44 frames at an interval of 43 -- which is one
#: click lost at the edge of hearing, where the next was never due sooner and
#: is the floor for any rule that ever drops one -- worst run of lost clicks
#: **three**, and runs of three or more down from 50 to 4.
#:
#: The ceiling below is a regression guard and not a blessing: it catches a
#: change that makes the starvation much worse. It is kept at 120 rather than
#: dropped to the new 44, because a single run can legitimately end inside a
#: long silence at the edge of hearing and this test is not the place to find
#: that out.
MEASURED_WORST_QUIET = 44
MEASURED_WORST_RUN = 3
QUIET_CEILING = 120


@pytest.mark.parametrize("bot", ["listener", "undertaker", "wanderer"])
def test_how_long_the_sonar_goes_quiet_is_measured_every_run(bot):
    """**The measurement the ruling asked this slice to take.**

    *When the sonar lands inside an effect* closed on the understanding that an
    effect owns the voice, and left exactly one thing open: a bite is five
    frames and bites arrive fastest when the sonar does, so can a *run* of
    effects silence the warning for long enough to matter?

    It can, and what it cost was six clicks in a row in the second before a
    bite. The grace window is the answer (issue #57) and the figures are in
    `MEASURED_WORST_QUIET` above.

    **What this test guards is the run of lost clicks, not the frames.** A
    limit in frames cannot be met by any build that drops a click at all, since
    one drop at the edge of hearing is 46 frames of silence by arithmetic; how
    many clicks in a row the player lost, at the rate they were coming, is the
    figure the ruling was made on and the one that can regress.
    """
    from spikes import spike_driver, bots

    worst = 0
    for seed in SEEDS:
        run = spike_driver.drive(bots.make(bot, seed=seed), seed=seed)
        figures = run.voice.stats()
        assert figures["sonar_quiet_frames"] == run.voice.clicks.quiet
        if run.voice.clicks.quiet:
            # A silence always has a rate attached, or the frames cannot be
            # read: one click lost at the edge of hearing is 46 frames by
            # arithmetic and is nothing like four lost at contact.
            assert figures["sonar_quiet_interval"] > 0
        worst = max(worst, run.voice.clicks.quiet)
        assert run.voice.clicks.longest_run <= MEASURED_WORST_RUN, (
            f"{bot} on seed {seed} lost "
            f"{run.voice.clicks.longest_run} clicks in a row; the grace "
            f"window was ruled on a worst case of {MEASURED_WORST_RUN}")
    assert worst <= QUIET_CEILING, (
        f"{bot} starved the sonar for {worst} frames, far past the "
        f"{MEASURED_WORST_QUIET} this slice measured and the "
        f"{sounds.QUIET_LIMIT} the ruling flags")


def test_silence_in_an_empty_room_is_not_starvation():
    """The wrong version of this figure would have reopened a design thread on
    the strength of a bot walking away from every Cleg in the building.

    It counted a drop and then went on counting for as long as the run lasted,
    because it never asked whether the sonar still had anything to say: 1,111
    frames of "starvation" in a room with nothing in it. `buzz.NEVER` closes
    the measurement now.
    """
    voice = sounds.Voice()
    voice.update(False, False, [(M.SFX_GAME_OVER, 1)])
    voice.update(True, False, (), buzz.interval_for(0))
    assert voice.clicks.dropped == 1 and voice.clicks.quiet == 1
    for _ in range(500):
        voice.update(False, False, (), buzz.NEVER)
    assert voice.clicks.quiet == 1, "an empty room was counted as a silence"
