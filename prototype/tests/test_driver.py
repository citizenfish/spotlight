"""The headless driver and the two run reports.

Issue #17, the enabling issue for phase 2. Every number in the phase-0 review
came from monkey-patching the loop to fake a headless run; none of that code was
kept and none of it was reviewed. These tests are the difference between that
and a supported tool.

The four things they hold down:

* **It drives the real loop.** Not a copy, not a model. The test counts calls to
  `Session.step` and checks the run's constants are the game's constants.
* **A seed names a run.** Same seed, same bot, same numbers -- otherwise nothing
  measured across seeds means anything.
* **Two artefacts, two readers.** The JSON compares across seeds; the log is
  five or six lines of English with no percentages in it, because the user reads
  it aloud while a tester remembers.
* **It works with no host.** No window, no audio, no pygame -- which is a
  stronger statement than working under `SDL_VIDEODRIVER=dummy`, and is checked
  in a subprocess with that variable set.
"""

import json
import os
import subprocess
import sys

import pytest

from spikes import bots, rescue as rescue_mod, report, scene, session
from spikes import spike_driver as driver


def test_the_driver_runs_the_real_loop(monkeypatch):
    """No parallel simulation. `Session.step` is the only way a frame advances.

    A model of the game is a thing that can be right about a game that does not
    exist, and the whole reason this issue was raised is that the numbers we
    had came from one.
    """
    calls = []
    real = session.Session.step
    monkeypatch.setattr(session.Session, "step",
                        lambda self, intent=session.IDLE:
                        calls.append(1) or real(self, intent))
    run = driver.drive(bots.make("statue"), seed=1, frames=250)
    assert len(calls) == run.frame == 250


def test_the_driver_uses_the_real_constants():
    """Not a smaller room or a shorter clock. The numbers have to be about the
    game a tester will be handed."""
    run = driver.drive(bots.make("statue"), seed=1, frames=10)
    assert run.total == len(scene.WORKERS)
    assert run.blood_full == session.BLOOD_FULL
    assert run.lives == session.LIVES
    # The authored ladder, not a fallback and not a computed one. A driver run
    # on `rescue.WORKER_BLOOD` for everybody would be measuring the game that
    # issue #18 removed.
    assert [w.start_blood for w in run.rescue.workers] == \
        [blood for _x, _y, blood in scene.WORKERS]
    assert len(set(w.start_blood for w in run.rescue.workers)) == run.total
    assert len(run.swarm.clegs) == len(scene.CLEGS)


def test_the_same_seed_gives_the_same_numbers():
    a = report.results(driver.drive(bots.make("wanderer", seed=3), seed=3,
                                    frames=1500))
    b = report.results(driver.drive(bots.make("wanderer", seed=3), seed=3,
                                    frames=1500))
    assert a["metrics"] == b["metrics"]
    assert a["people"] == b["people"]
    assert a["events"] == b["events"]


def test_different_seeds_give_different_numbers():
    a = report.results(driver.drive(bots.make("wanderer", seed=1), seed=1,
                                    frames=3000))
    b = report.results(driver.drive(bots.make("wanderer", seed=2), seed=2,
                                    frames=3000))
    assert a["metrics"] != b["metrics"]


def test_the_frame_limit_is_an_ending_of_its_own():
    """A run stopped by the driver did not end; it has to say so rather than
    be counted as a loss."""
    run = driver.drive(bots.make("statue"), seed=1, frames=100)
    assert run.over == session.FRAME_LIMIT
    assert run.frame == 100


def test_the_driver_can_run_the_real_drawing_code():
    """So that a change which breaks rendering fails here and not in front of a
    tester. Drawing is portable, so this needs no host either."""
    from spotlight.core.screen import Screen
    screen = Screen()
    driver.drive(bots.make("wanderer", seed=1), seed=1, frames=120, draw=True,
                 screen=screen)
    assert any(screen.pixels)


# --- the machine-readable report -------------------------------------------


@pytest.mark.parametrize("name", ["statue", "wanderer", "listener", "oracle"])
def test_every_run_reports_the_same_shape(name):
    """Comparable across seeds means comparable across everything: the keys do
    not depend on what happened."""
    run = driver.drive(bots.make(name, seed=2), seed=2, frames=2500)
    results = report.results(run, bot=name)
    baseline = report.results(driver.drive(bots.make("statue"), seed=9,
                                           frames=300), bot="statue")
    assert set(results) == set(baseline)
    assert set(results["metrics"]) == set(baseline["metrics"])


def test_the_metrics_are_scalars_so_they_tabulate():
    run = driver.drive(bots.make("wanderer", seed=1), seed=1, frames=2000)
    for key, value in report.metrics(run).items():
        assert value is None or isinstance(value, int), key


def test_the_metrics_cover_the_difficulty_targets():
    """The eight targets in the phase-0 review, each stated in some number.

    Named here so that a target cannot quietly become unmeasurable: if somebody
    removes one of these, this test says which conversation it belonged to.
    """
    run = driver.drive(bots.make("statue"), seed=1, frames=7500)
    m = report.metrics(run)
    for key in ("rescued",                      # T1, T4
                "seconds", "torch_seconds",     # T2, T6
                "blood_lost",                   # T3
                "tries_lost", "first_try_lost_seconds",   # T4, T5
                "first_death_seconds", "last_death_seconds",
                "death_spread_seconds",         # T7
                "first_attachment_seconds",     # T8
                "blood_lost_first_minute", "blood_lost_second_minute"):
        assert key in m, key


def test_the_report_says_what_became_of_everybody():
    """The bug that made this issue: a run of seven reported four people and
    lost the three in the tail."""
    run = driver.drive(bots.make("wanderer", seed=4), seed=4)
    results = report.results(run, bot="wanderer")
    assert len(results["people"]) == run.total
    assert results["tally_adds_up"]
    outcomes = [p["outcome"] for p in results["people"]]
    assert all(o in (report.OUT, report.DIED_WAITING, report.DIED_FOLLOWING,
                     report.STILL_WAITING, report.STILL_FOLLOWING)
               for o in outcomes)
    assert len(outcomes) == 7


def test_a_death_records_which_room_it_happened_in():
    """One room today. Issue #21 adds the second, and both reports already have
    somewhere to put the answer to the question the user will ask."""
    run = driver.drive(bots.make("statue"), seed=1)
    for person in report.results(run)["people"]:
        assert person["room"] == scene.ROOM_NAME
    for event in report.results(run)["events"]:
        assert event["room"]


def test_the_event_log_is_kept_in_full():
    """Because the question phase 2 wants to ask has not been thought of yet,
    and deriving it from a saved run beats re-running one and hoping the
    constants have not moved."""
    run = driver.drive(bots.make("wanderer", seed=1), seed=1, frames=3000)
    events = report.results(run)["events"]
    assert len(events) == len(run.log)
    assert all(set(e) == {"frame", "seconds", "kind", "who", "count", "room"}
               for e in events)


# --- the human log ----------------------------------------------------------


def test_the_human_log_is_a_handful_of_lines():
    """Five or six lines. A memory aid that has to be studied is not one."""
    for name, seed in (("statue", 1), ("wanderer", 4), ("listener", 2),
                       ("oracle", 3)):
        run = driver.drive(bots.make(name, seed=seed), seed=seed)
        lines = report.human(run, bot=name)
        assert 3 <= len(lines) <= 8, (name, lines)


def test_the_human_log_is_words_not_numbers():
    """No percentages and no blood per rescue. Those are real numbers and they
    live in the other artefact; the user is holding a conversation."""
    run = driver.drive(bots.make("wanderer", seed=4), seed=4)
    text = " ".join(report.human(run, bot="wanderer")).lower()
    assert "%" not in text
    assert "blood" not in text
    assert "attach" not in text


def test_the_human_log_says_who_and_roughly_when_and_how_it_ended():
    run = driver.drive(bots.make("oracle", seed=3), seed=3)
    lines = report.human(run, bot="oracle")
    text = " ".join(lines)
    assert "Seed 3" in lines[0]
    assert "Got out" in text
    assert "about" in text, "times are rounded, because 'roughly when' is the ask"
    assert lines[-1] == report.ENDING_WORDS[run.over]


def test_the_human_log_names_where_somebody_was():
    """"you lost the one in the top corner at about a minute" is the question
    the user wants to be able to ask."""
    run = driver.drive(bots.make("statue"), seed=1)
    text = " ".join(report.human(run, bot="statue"))
    assert "the one in" in text or "all seven" in text


def test_the_human_log_calls_out_a_follower_who_died():
    """Somebody who died while you were leading them out is a different story
    from somebody you never reached, and it is the one the design is about."""
    run = driver.drive(bots.make("wanderer", seed=4), seed=4)
    people = report.people(run)
    assert any(p["outcome"] == report.DIED_FOLLOWING for p in people), \
        "seed 4 is chosen because somebody dies in the tail"
    text = " ".join(report.human(run, bot="wanderer"))
    assert "following you" in text


def test_two_people_in_the_same_corner_are_told_apart():
    run = driver.drive(bots.make("statue"), seed=1)
    records = report.people(run)
    clauses = report._name_them(records, rooms=1)
    assert len(set(clauses)) == len(clauses)


def test_places_are_the_words_a_person_would_use():
    assert report.place(1, 1) == "the top left"
    assert report.place(30, 20) == "the bottom right"
    assert report.place(16, 11) == "the middle of the room"
    assert report.place(16, 1) == "the top middle"


def test_times_are_rounded_to_something_a_tester_remembers():
    assert report.roughly(67) == "about 1:10"
    assert report.roughly(3) == "about 0:00"
    assert report.clock(92) == "1:32"


# --- the command line -------------------------------------------------------


def test_the_command_line_writes_both_reports(tmp_path):
    code = driver.main(["--bot", "statue", "--seed", "3", "--frames", "300",
                        "--out", str(tmp_path)])
    assert code == 0
    written = sorted(p.name for p in tmp_path.iterdir())
    assert len(written) == 2
    assert any(n.endswith(".json") for n in written)
    assert any(n.endswith(".txt") for n in written)
    data = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert data["seed"] == 3 and data["bot"] == "statue"
    assert next(tmp_path.glob("*.txt")).read_text().startswith("Seed 3")


def test_the_command_line_runs_several_seeds_and_summarises(tmp_path, capsys):
    driver.main(["--bot", "listener", "--seed", "20", "--seeds", "3",
                 "--frames", "400", "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert "Seed 20" in out and "Seed 22" in out
    assert "ending" in out and "1stbite" in out
    assert len(list(tmp_path.glob("*.json"))) == 3


def test_the_command_line_can_check_reproducibility(capsys):
    assert driver.main(["--bot", "wanderer", "--seed", "5", "--frames", "600",
                        "--repeat", "--no-files"]) == 0


def test_the_command_line_takes_a_script(capsys):
    driver.main(["--script", "200R 100D", "--frames", "400", "--no-files"])
    assert "Seed" in capsys.readouterr().out


def test_it_runs_headless_in_a_subprocess():
    """The acceptance criterion, checked the way it will actually be used.

    It passes for a stronger reason than the dummy driver: nothing in the
    driver, the session, the bots or the reports imports pygame at all.
    """
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    done = subprocess.run(
        [sys.executable, "-m", "spikes.spike_driver", "--bot", "oracle",
         "--seed", "7", "--frames", "1200", "--no-files"],
        cwd=root, env=env, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert "Seed 7" in done.stdout
    assert "pygame" not in done.stdout.lower()


def test_the_driver_needs_no_host_at_all():
    """Stronger than the dummy driver, and the reason the tester can run this
    on anything: the portable half of the prototype is the whole run."""
    for module in (session, bots, report):
        source = open(module.__file__).read()
        assert "import pygame" not in source


# --- blood by lure (issue #22) ---------------------------------------------

def _without_the_lure_buckets(metrics: dict) -> dict:
    return {k: v for k, v in metrics.items()
            if not (k.startswith("blood_by_") or k.startswith("bites_by_"))}


@pytest.mark.parametrize("seed", (1, 2, 3))
def test_the_attribution_hook_changes_nothing_about_the_run(monkeypatch, seed):
    """**The test issue #22 states.** Every metric identical with the hook
    present and absent, on the same seed.

    A measurement that perturbs what it measures is worse than no measurement,
    because it is believed. The hook is two writes -- the source at acquisition
    and a counter on the way past -- and neither is read by anything that
    decides where a fly goes. This drives a whole run both ways and compares
    the metrics *and* the event log, frame by frame.
    """
    from spikes import clegs as clegs_mod

    def play():
        run = driver.drive(bots.make("wanderer", seed=seed), seed=seed,
                           frames=4000)
        results = report.results(run, bot="wanderer")
        return _without_the_lure_buckets(results["metrics"]), results["events"]

    with_hook = play()

    # The hook, removed: `commit` reverts to what it was before the issue, and
    # the counters stop counting.
    monkeypatch.setattr(clegs_mod.Cleg, "commit",
                        lambda self, cell, kind: setattr(self, "goal", cell))
    monkeypatch.setattr(clegs_mod.Swarm, "_bill",
                        lambda self, cleg, bites=0, blood=0: None)
    without_hook = play()

    assert with_hook[0] == without_hook[0]
    assert with_hook[1] == without_hook[1]


def test_blood_and_bites_are_attributable_per_lure_in_the_report():
    """The breakdown is in the machine-readable report, in flat integer keys,
    so blood-by-lure tabulates across seeds like everything else."""
    from spikes import sources

    run = driver.drive(bots.make("wanderer", seed=1, light=True), seed=1,
                       frames=4000)
    m = report.metrics(run)
    for lure in sources.LURE_NAMES:
        assert isinstance(m[f"blood_by_{lure}"], int)
        assert isinstance(m[f"bites_by_{lure}"], int)
    assert sum(m[f"blood_by_{l}"] for l in sources.LURE_NAMES) == m["blood_lost"]
    assert sum(m[f"bites_by_{l}"] for l in sources.LURE_NAMES) == m["attachments"]


def test_the_searchlight_can_be_told_from_the_torch():
    """The number the hook exists for. The claim that the beam delivers three
    quarters of the swarm was inferred by correlating attachments with the beam
    passing nearby; this is the same quantity measured at the point of
    attachment.

    Asserted loosely and on one bot, because it is a measurement rather than a
    rule: what is pinned is that the buckets can actually tell two lures apart,
    so a future run that put everything in one of them would be read as a
    finding rather than as the hook being broken.
    """
    from spikes import sources

    dark = report.metrics(driver.drive(bots.make("statue", seed=1, light=False),
                                       seed=1, frames=7500))
    assert dark[f"blood_by_{sources.LURE_NAMES[sources.LURE_TORCH]}"] == 0, \
        "a torch that was never lit cannot have cost anything"
    assert dark["blood_by_beam"] > dark["blood_by_glow"]

    lit = report.metrics(driver.drive(bots.make("statue", seed=2, light=True),
                                      seed=2, frames=7500))
    assert lit["blood_by_torch"] > 0, "a burning torch recruits, and is billed"
