"""The host half of the speaker: the synth, the bank and the run render.

Issue #54. `spike_sound` is the only part of the audio that does not port, and
these tests are about the two things a host has to get right: that it makes a
noise at all with no device present, and that **the WAV of a run is a recording
of the performance the game gave** rather than a second performance derived
afterwards from the event log. Those are not the same file and only one of them
is evidence.
"""

import os
import wave

from spikes import moments as M, sounds, spike_driver, spike_sound
from spikes.session import Session


def _samples(path):
    with wave.open(path) as handle:
        assert handle.getnchannels() == 1 and handle.getsampwidth() == 2
        assert handle.getframerate() == spike_sound.RATE
        return handle.getnframes()


def test_a_frame_of_audio_is_a_frame_of_the_game():
    """882 samples at 44.1kHz and 50Hz, exactly, which is why this is all
    integers."""
    assert spike_sound.FRAME_SAMPLES == 882
    assert len(spike_sound.SILENT_FRAME) == 2 * 882


def test_every_effect_renders_one_block_per_frame():
    for sound, effect in sounds.EFFECTS.items():
        blocks = spike_sound.effect_frames(sound)
        assert len(blocks) == effect.frames, M.SOUND_NAMES[sound]
        assert all(len(b) == len(spike_sound.SILENT_FRAME) for b in blocks)
        assert any(any(b) for b in blocks), "an effect rendered to silence"


def test_the_synth_carries_its_phase_across_frames():
    """An effect is a glide cut into twenty-millisecond pieces. Restarting the
    cycle each frame would put a click at 50Hz through every sound in the game
    -- and the Z80 does not, because it is mid-delay when the interrupt fires.
    """
    synth = spike_sound.Synth()
    note = sounds.Note(sounds.TONE, sounds.period_of(440),
                       sounds.period_of(440), 2)
    synth.frame(note)
    assert 0 < synth.pos < synth.cycle, "the frame ended on a cycle boundary"


def test_the_two_built_voices_are_padded_to_a_frame_and_not_stretched():
    """The frame is the unit of arbitration, so the rest of a click's frame is
    silence -- which is the sketch's own finding about what the sonar costs the
    music."""
    bank = spike_sound.Bank()
    assert len(bank.click) == len(spike_sound.SILENT_FRAME)
    assert len(bank.tick) == len(spike_sound.SILENT_FRAME)
    from spikes import spike_buzz
    raw = spike_buzz.click_wave(stereo=False)
    assert bank.click[:len(raw)] == raw, "the click was resampled"
    assert not any(bank.click[len(raw):]), "the pad is not silence"


def test_the_bank_writes_every_file_headless(tmp_path):
    """`--bank` on a machine with no audio device at all: it writes the files
    and says nothing.

    Twenty-three now (issue #55): the nineteen the effects round wrote, plus
    the two tunes and the two files that are about the dropout rather than
    about the tune. `ostinato-with-sonar.wav` is the one the design's claim
    that *the music thinning out is itself a warning* gets judged on, so a
    bank without it is a bank that cannot answer the question it exists for.
    """
    paths = spike_sound.bank_files(str(tmp_path))
    names = {os.path.basename(p) for p in paths}
    for name in M.SOUND_NAMES:
        assert f"{name.lower().replace('_', '-', 1)}.wav" in names
    assert {"sonar-edge.wav", "sonar-halfway.wav", "sonar-contact.wav",
            "tick.wav"} <= names
    assert {"theme.wav", "ostinato.wav", "ostinato-under-load.wav",
            "ostinato-with-sonar.wav"} <= names
    assert len(paths) == 23, \
        "fourteen effects, three sonar rates, a tick, a set, and four of music"
    for path in paths:
        assert _samples(path) > 0


def test_the_sonar_files_are_the_three_rates_the_counter_gives(tmp_path):
    """46 frames at the edge, 29 halfway, 8 on contact -- and they come from
    `buzz.Sonar` rather than from a gap written out in the host."""
    lengths = {}
    for name, distance in spike_sound.SONAR_RATES:
        data = spike_sound.sonar_wave(distance, clicks=4)
        lengths[name] = len(data) // len(spike_sound.SILENT_FRAME)
    assert lengths["contact"] == 4 * 8
    assert lengths["halfway"] == 4 * 29
    assert lengths["edge"] == 4 * 46


def test_the_tick_file_is_a_real_bodys_twenty_seconds():
    """Fresh to about to turn, from a real `Worker` and a real `Ticker`: the
    quickening is the information and it belongs to the body."""
    from spikes import rescue

    frames = len(spike_sound.tick_wave()) // len(spike_sound.SILENT_FRAME)
    assert frames == rescue.BODY_FRAMES == 1000


def test_a_run_renders_from_the_decisions_the_game_made(tmp_path):
    """**The point of the file.** The render is driven by the recorded
    per-frame decisions, so a click that was dropped is missing from the WAV
    and an effect that was cut off is short in it. A render that re-derived the
    arbitration from the log would be a different performance."""
    recorder = spike_sound.Recorder()
    run = spike_driver.drive(seed=1, frames=500, on_sound=recorder)
    assert len(recorder.frames) == run.frame
    data = recorder.render()
    assert len(data) == run.frame * len(spike_sound.SILENT_FRAME)

    # Every sounding frame in the render is the frame the arbiter named, and
    # every silent one is silent.
    bank = spike_sound.Bank()
    for i, decision in enumerate(recorder.frames):
        block = data[i * len(spike_sound.SILENT_FRAME):
                     (i + 1) * len(spike_sound.SILENT_FRAME)]
        assert block == bank.frame(decision)
    assert any(d[0] != sounds.NOTHING for d in recorder.frames)

    path = spike_sound.write_wav(str(tmp_path / "run.wav"), data)
    assert _samples(path) == run.frame * spike_sound.FRAME_SAMPLES


def test_a_cut_effect_is_short_in_the_render():
    """A priority-1 arrival stops a priority-0 sound dead, and the file says
    so: the frames it never got are not in it."""
    voice = sounds.Voice()
    voice.update(False, False, [(M.SFX_TORCH_OUT, 0)])
    heard = [voice.decision()]
    voice.update(False, False)
    heard.append(voice.decision())
    voice.update(False, False, [(M.SFX_WORKER_DIED, 1)])
    heard.append(voice.decision())
    assert [d[2] for d in heard] == [0, 1, 0]
    assert heard[-1][1] == M.SFX_WORKER_DIED


def test_a_punctured_effect_renders_as_a_hole_and_not_as_a_delay(tmp_path):
    """**What the grace window sounds like** (issue #57): the click is in the
    file where the click happened, the frame it took is missing, and every
    frame after it is the frame of the sound it always was.

    The alternative -- the effect resuming where it left off and running a
    frame late -- would be the same sound stretched, which is a different
    sound. The render is built from the recorded decisions, so this is the
    file, not a description of it.
    """
    voice = sounds.Voice()
    heard = []
    voice.update(False, False, [(M.SFX_HATCHED, 0)])     # 30 frames
    heard.append(voice.decision())
    for _ in range(sounds.EFFECTS[M.SFX_HATCHED].frames - 1):
        # A click on every frame: inside the window they are dropped, past it
        # every single one is heard.
        voice.update(True, False)
        heard.append(voice.decision())
    kinds = [d[0] for d in heard]
    assert kinds[:sounds.GRACE_FRAMES] == [sounds.EFFECT] * sounds.GRACE_FRAMES
    assert set(kinds[sounds.GRACE_FRAMES:]) == {sounds.CLICK}
    assert voice.update(False, False) == sounds.NOTHING, \
        "the effect ran on past its length"

    bank = spike_sound.Bank()
    data = b"".join(bank.frame(d) for d in heard)
    frames = spike_sound.effect_frames(M.SFX_HATCHED)
    block = len(spike_sound.SILENT_FRAME)
    for i in range(sounds.GRACE_FRAMES):
        assert data[i * block:(i + 1) * block] == frames[i]
    assert data[sounds.GRACE_FRAMES * block:
                (sounds.GRACE_FRAMES + 1) * block] == bank.click


def test_the_live_speaker_picks_a_punctured_sound_up_where_it_left_off():
    """A Pygame stand-in with no equivalent on the target.

    pygame is handed a whole effect at once, so the click that punches the hole
    stops the channel and the rest of the sound has to be handed over again.
    On the Spectrum the player routine reads the next note out of the table and
    there is nothing to resume. Tested through the tail builder rather than
    through a device, because the suite runs with no device at all.
    """
    speaker = spike_sound.Speaker()
    if not speaker.open():
        return                          # no mixer here; nothing to resume with
    tail = speaker._tail(M.SFX_HATCHED, 20)
    again = speaker._tail(M.SFX_HATCHED, 20)
    assert tail is again, "a tail was rebuilt instead of kept"
    frames = spike_sound.effect_frames(M.SFX_HATCHED)
    expected = sum(len(f) for f in frames[20:]) // 2
    # The mixer may have opened in stereo, in which case every sample is
    # doubled; either way the tail is the rest of the sound and nothing else.
    assert tail.get_length() > 0
    assert expected in (int(tail.get_length() * spike_sound.RATE + 0.5),
                        int(tail.get_length() * spike_sound.RATE))
    speaker.close()


def test_the_speaker_is_silent_and_harmless_with_no_device():
    """Sound is the first thing to go on a machine that cannot make a noise --
    and every headless run in this project depends on that being true."""
    speaker = spike_sound.Speaker()
    speaker.open()                      # may or may not find a device; neither
    run = Session(seed=1)               # is an error
    run.step()
    speaker.play(run.voice)
    speaker.play(None)
    speaker.close()


def test_the_driver_writes_a_bank_and_a_run_wav(tmp_path, capsys):
    """Both flags, end to end, headless."""
    assert spike_driver.main(["--bank", str(tmp_path / "bank")]) == 0
    assert len(list((tmp_path / "bank").iterdir())) == 23

    wav = tmp_path / "run.wav"
    assert spike_driver.main([
        "--bot", "statue", "--frames", "300", "--no-files",
        "--wav", str(wav)]) == 0
    assert _samples(str(wav)) == 300 * spike_sound.FRAME_SAMPLES
    assert "run.wav" in capsys.readouterr().out


def test_more_than_one_seed_gets_more_than_one_file(tmp_path):
    """A file whose name does not say which run it came from is a file nobody
    can act on -- the same rule the snapshots have."""
    wav = tmp_path / "run.wav"
    assert spike_driver.main([
        "--bot", "statue", "--seeds", "2", "--frames", "100", "--no-files",
        "--wav", str(wav)]) == 0
    written = sorted(p.name for p in tmp_path.iterdir())
    assert len(written) == 2 and all("seed" in name for name in written)
