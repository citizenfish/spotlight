"""What a run came to, for two readers who want different things.

The phase-0 review settled this and it is the reason there are two functions
here rather than one file with everything in it:

* **`results()` is for the tester agent.** Numbers, in a shape that compares
  across seeds. It is what phase 2 tunes against, so it carries every quantity
  the eight difficulty targets are stated in, plus the whole event log so that a
  question nobody has thought of yet can still be answered from an old run.
* **`human()` is for the user, in conversation.** Five or six lines, in words,
  in order: who got out, who did not and roughly when, how it ended, how long it
  took. **The tester never reads it.** The user reads it while talking to the
  person who played, so that they can say *you lost the one in the top corner at
  about a minute -- did you know they were there?* and have them remember.

That last sentence is the whole specification for the human log, and it rules
things out: no percentages, no blood per rescue, no attachment counts. Those are
real numbers and they belong in the other artefact. A memory aid that has to be
studied is not a memory aid.

Both are built from `Session.log`, which is the run's own record of what
happened and to whom. Nothing is reconstructed by guesswork: the spike printed
counts rather than people, which is exactly why a run could report four workers
"never found" without being able to say what became of the other three.
"""

from spotlight.core.constants import COLS

from . import rescue as rescue_mod, scene, session as session_mod, sources
from .layout import PLAY_ROWS
from .rescue import HEIGHT as WORKER_HEIGHT

FRAME_RATE = 50

# --- outcomes --------------------------------------------------------------
# What became of one person. Five, not three, because "died" and "still inside"
# each split on whether they were following you at the time -- and that is the
# difference the design is most interested in: a follower who dies is one you
# reached and could not get out.

OUT = "out"
DIED_WAITING = "died_waiting"
DIED_FOLLOWING = "died_following"
STILL_WAITING = "still_waiting"
STILL_FOLLOWING = "still_following"

#: How each outcome reads in the human log, as a clause about one person.
OUTCOME_WORDS = {
    OUT: "got out",
    DIED_WAITING: "died waiting",
    DIED_FOLLOWING: "died following you",
    STILL_WAITING: "was still waiting",
    STILL_FOLLOWING: "was still following you",
}

#: How each ending reads as a sentence.
ENDING_WORDS = {
    session_mod.ALL_OUT: "It ended with everybody out.",
    session_mod.NOBODY_LEFT: "It ended when there was nobody left to save.",
    session_mod.NO_LIVES: "It ended when you bled out for the last time.",
    session_mod.FRAME_LIMIT: "It was stopped when the frame limit ran out.",
    session_mod.ABANDONED: "It was stopped.",
}


def place(cx: int, cy: int) -> str:
    """Roughly where in the room a cell is, in the words a person would use.

    Thirds, because "the one in the top left" is how somebody who played for
    ninety seconds remembers a position, and a cell reference is not. The room
    is 32x22 so the thirds are uneven by a cell; nobody will notice and it does
    not matter what the boundary is, only that the answer is stable.
    """
    down = "top" if cy < PLAY_ROWS // 3 else \
        "bottom" if cy >= 2 * PLAY_ROWS // 3 else "middle"
    across = "left" if cx < COLS // 3 else \
        "right" if cx >= 2 * COLS // 3 else "centre"
    if down == "middle" and across == "centre":
        return "the middle of the room"
    if down == "middle":
        return f"the {across}-hand side"
    if across == "centre":
        return f"the {down} middle"
    return f"the {down} {across}"


def clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def roughly(seconds: int) -> str:
    """A time rounded to ten seconds, because "roughly when" is the ask.

    A tester does not remember 1:07. They remember about a minute, and asking
    them about 1:07 invites them to agree with a number rather than recall a
    moment.
    """
    return f"about {clock((seconds + 5) // 10 * 10)}"


def _seconds(frame: int) -> int:
    return frame // FRAME_RATE


def people(run) -> list[dict]:
    """One record per worker: who they were, what happened, and when.

    Built from the log, so the answer is the same whether it is asked at the end
    of a run or from a saved file a week later.
    """
    total = run.total
    freed = {}
    delivered = {}
    died = {}
    died_room = {}
    for event in run.log:
        if event.who is None:
            continue
        if event.kind == session_mod.FREED:
            freed[event.who] = event.frame
        elif event.kind == session_mod.DELIVERED:
            delivered[event.who] = event.frame
        elif event.kind == session_mod.WORKER_DIED:
            died[event.who] = event.frame
            died_room[event.who] = event.room

    records = []
    for i in range(total):
        worker = run.rescue.workers[i]
        start_cx = scene.WORKERS[i][0] // 8
        start_cy = (scene.WORKERS[i][1] + WORKER_HEIGHT - 1) // 8
        if i in delivered:
            outcome = OUT
        elif i in died:
            outcome = DIED_FOLLOWING if i in freed else DIED_WAITING
        elif i in freed:
            outcome = STILL_FOLLOWING
        else:
            outcome = STILL_WAITING
        records.append({
            "who": i,
            # Where they were trapped, not where they ended up. It is what the
            # player would remember and what the user wants to ask about.
            "found_in": place(start_cx, start_cy),
            "room": died_room.get(i, run.room),
            "outcome": outcome,
            "freed_at": _seconds(freed[i]) if i in freed else None,
            "out_at": _seconds(delivered[i]) if i in delivered else None,
            "died_at": _seconds(died[i]) if i in died else None,
            "blood_left": worker.blood,
            # Which rung of the authored ladder this person was given, and how
            # long that bought them. Reported because a staggered clock is only
            # readable if you can see who was on the short one -- "the one who
            # died first" is a different claim from "the one with sixty
            # seconds died first". Issue #18.
            "blood_start": worker.start_blood,
            "life_seconds": worker.start_blood * rescue_mod.BLEED_EVERY
            // FRAME_RATE,
        })
    return records


def metrics(run) -> dict:
    """Every number the difficulty targets are stated in, and nothing derived.

    Flat and all-integer on purpose: this is the part that gets tabulated across
    seeds, and a table wants scalars. `None` means it never happened, which is
    itself an answer -- "no first bite" is not the same as "first bite at zero".
    """
    log = run.log
    first = {}
    for event in log:
        first.setdefault(event.kind, event.frame)

    deaths = [e.frame for e in log if e.kind == session_mod.WORKER_DIED]
    rescues = [e.frame for e in log if e.kind == session_mod.DELIVERED]
    minute = FRAME_RATE * 60
    drained = [(e.frame, e.count) for e in log if e.kind == session_mod.DRAINED]

    def when(kind):
        return _seconds(first[kind]) if kind in first else None

    # What each lure cost, at the point of attachment rather than inferred
    # from timing (issue #22). Flat scalars with the bucket in the key, so
    # blood-by-lure tabulates across seeds like everything else here. The
    # `_none` bucket is bites nothing lured -- a fly that fed, lost interest,
    # and blundered back onto the player -- and it is an answer, not a gap.
    by_lure = {}
    for kind, lure in enumerate(sources.LURE_NAMES):
        by_lure[f"blood_by_{lure}"] = run.swarm.blood_by_source[kind]
        by_lure[f"bites_by_{lure}"] = run.swarm.bites_by_source[kind]

    return {
        **by_lure,
        "frames": run.frame,
        "seconds": run.seconds,
        "workers_total": run.total,
        "rescued": run.rescued,
        "died": run.lost,
        "still_inside": run.inside,
        "still_following": len(run.rescue.tail),
        "blood_lost": run.tally.blood_lost,
        "blood_lost_first_minute": sum(c for f, c in drained if f <= minute),
        "blood_lost_second_minute":
            sum(c for f, c in drained if minute < f <= 2 * minute),
        "attachments": run.tally.attachments,
        "first_attachment_seconds": when(session_mod.BITTEN),
        "tries_lost": session_mod.LIVES - run.lives,
        "first_try_lost_seconds": when(session_mod.LIFE_LOST),
        "torch_seconds": run.tally.lit_seconds,
        "dark_seconds": run.seconds - run.tally.lit_seconds,
        "torch_percent": run.tally.lit_percent,
        "sprays_fired": run.tally.sprays,
        "clegs_killed": run.tally.swatted,
        "clegs_left": len(run.swarm.clegs),
        "spotlight_swaps": run.kit.swaps,
        "first_rescue_seconds": _seconds(rescues[0]) if rescues else None,
        "last_rescue_seconds": _seconds(rescues[-1]) if rescues else None,
        "first_death_seconds": _seconds(deaths[0]) if deaths else None,
        "last_death_seconds": _seconds(deaths[-1]) if deaths else None,
        # Target T7: losses must be sequenced. Zero means everybody died in the
        # same instant, which is what the phase-0 review measured and why #18
        # exists.
        "death_spread_seconds":
            _seconds(deaths[-1] - deaths[0]) if deaths else None,
        # Target T7 as restated in *Difficulty targets*: **no two deaths within
        # twenty seconds of each other**. First-to-last is not that quantity --
        # seven deaths spread over sixty seconds are ten seconds apart, which
        # is half a body window -- so the number the target is actually stated
        # in is the shortest gap between consecutive deaths. `None` when fewer
        # than two people died, because there was no gap to measure.
        "closest_deaths_seconds":
            _seconds(min(b - a for a, b in zip(deaths, deaths[1:])))
            if len(deaths) > 1 else None,
    }


def results(run, bot: str = "", label: str = "") -> dict:
    """The machine-readable run: metadata, metrics, people, and the whole log.

    The log is included in full because it is small and because the question
    phase 2 wants to ask has not been thought of yet. Deriving a new number
    from a saved run beats re-running it and hoping the constants have not
    moved underneath.
    """
    return {
        "seed": run.seed,
        "bot": bot,
        "label": label,
        "room": run.room,
        "ending": run.over,
        "tally_adds_up": run.tally_adds_up(),
        "metrics": metrics(run),
        "people": people(run),
        "events": [
            {"frame": e.frame, "seconds": e.seconds, "kind": e.kind,
             "who": e.who, "count": e.count, "room": e.room}
            for e in run.log
        ],
    }


#: Counting words, because a memory aid is prose. Past ten it is a number
#: again, and a room with more than ten people in it is a different problem.
_WORDS = ("nobody", "one", "two", "three", "four", "five", "six", "seven",
          "eight", "nine", "ten")


def _word(n: int) -> str:
    return _WORDS[n] if 0 <= n < len(_WORDS) else str(n)


def _name_them(records, rooms: int) -> list[str]:
    """"the one in the top left", and the room too once there is more than one.

    With one room, naming it every time is noise. With two -- issue #21 -- "you
    lost the one in the far room" is the question the user actually wants to
    ask, so the clause appears as soon as there is a choice to make. Nothing
    else in the log has to change when the second room lands.

    Two people can be trapped in the same third of the room, and calling both
    of them "the one in the top left" would leave the user unable to ask about
    either. The second becomes "another one in the top left", which is how a
    person would say it.
    """
    out, seen = [], set()
    for record in records:
        where = record["found_in"]
        if rooms > 1:
            where += f" in {record['room']}"
        clause = ("another one in " if where in seen else "the one in ") + where
        seen.add(where)
        out.append(clause)
    return out


def _join(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _wrap(text: str, width: int = 76) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    if line:
        lines.append(line)
    return lines


#: How many people a line names before it stops naming them. Four names with
#: four times in one sentence is a list, and a list is not a memory aid.
NAME_LIMIT = 3


def _sentence(prefix: str, records, rooms: int, key: str,
              total: int) -> str:
    """One line about one group of people, kept short enough to say out loud.

    Three cases, and they exist because the first draft produced a four-line
    sentence naming seven people at the same time, which nobody would read out
    and nobody could remember.
    """
    times = sorted(r[key] for r in records)
    if len(records) == total and total > 1:
        span = (f"at {roughly(times[0])}" if times[0] == times[-1]
                else f"between {roughly(times[0])} and {roughly(times[-1])}")
        return f"{prefix}: all {_word(total)} of them, {span}."
    named = [f"{clause} at {roughly(r[key])}"
             for clause, r in zip(_name_them(records, rooms), records)]
    if len(named) > NAME_LIMIT:
        rest = len(named) - NAME_LIMIT
        named = named[:NAME_LIMIT] + [
            f"{_word(rest)} more by {roughly(times[-1])}"]
    return f"{prefix}: {_join(named)}."


def human(run, bot: str = "", label: str = "") -> list[str]:
    """The run in five or six lines of English, in the order it happened.

    A memory aid for a conversation, not a data file. Everything in it is
    something the user could reasonably open with; anything they would have to
    interpret has been left in `results()` instead.
    """
    who = label or bot or "somebody"
    records = people(run)
    rooms = len({r["room"] for r in records} | {run.room})

    lines = [f"Seed {run.seed}, played by {who}. "
             f"The run lasted {clock(run.seconds)}."]

    out = sorted((r for r in records if r["outcome"] == OUT),
                 key=lambda r: r["out_at"])
    if out:
        lines += _wrap(_sentence("Got out", out, rooms, "out_at", run.total))
    else:
        lines.append("Nobody got out.")

    dead = sorted((r for r in records if r["died_at"] is not None),
                  key=lambda r: r["died_at"])
    if dead:
        lines += _wrap(_sentence("Died", dead, rooms, "died_at", run.total))
        # Somebody who died while you were leading them out is a different
        # story from somebody you never reached, and it is the one the design
        # cares most about. Said separately so it cannot be lost in a list.
        following = [r for r in dead if r["outcome"] == DIED_FOLLOWING]
        if following:
            lines += _wrap(
                f"{_word(len(following)).capitalize()} of them died while "
                f"following you: "
                f"{_join(_name_them(following, rooms))}.")
    else:
        lines.append("Nobody died.")

    left = [r for r in records
            if r["outcome"] in (STILL_WAITING, STILL_FOLLOWING)]
    if left:
        following = sum(1 for r in left if r["outcome"] == STILL_FOLLOWING)
        tail = (f", {_word(following)} of them still following you"
                if following else "")
        # Same rule as the other two lines: past three names it stops being a
        # sentence somebody would say and becomes a list.
        if len(left) == run.total:
            who_left = f"all {_word(run.total)} of them"
        elif len(left) > NAME_LIMIT:
            named = _name_them(left, rooms)
            who_left = _join(named[:NAME_LIMIT]
                             + [f"{_word(len(left) - NAME_LIMIT)} more"])
        else:
            who_left = _join(_name_them(left, rooms))
        lines += _wrap(f"Still in the building at the end: {who_left}{tail}.")

    lines.append(ENDING_WORDS.get(run.over, f"It ended: {run.over}."))
    return lines
