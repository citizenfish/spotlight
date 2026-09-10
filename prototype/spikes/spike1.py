"""The game, in a window: title screen, a room to search, an ending, and again.

Run it with:

    python -m spotlight            # --scale N to resize the window
                                   # --surge-frames N to try a surge length

**The game is four directions and two buttons.** That is the whole control
scheme and it is all a player ever touches:

    arrows   walk, and set your facing
    T        your carried spotlight, on and off
    SPACE    fire the flyspray ahead of you

    ESC      quit, from anywhere

**Everything else is inert unless the game is started with `--debug`.** There
are fourteen developer keys on ordinary letters and one of them, `F`, reveals
the entire room and everybody in it and holds it there. A tester who presses a
key to find out what it does could silently destroy the run we are asking them
about and never know they had. They are all still there and they all still
work; they are simply not reachable by accident. See `Debug`.

Those three are now **named on the title screen**, in words, because they used
to be named only here: the window opened straight into the opening flash and a
stranger had no way to learn that `T` existed at all. `T` is the bargain the
whole design rests on, so a player who does not know about it is not playing the
game. See `screens.py` for the wording and why it is worded that way.

A run has three endings and the screen says which: everyone out, nobody left to
save, or the last try gone. It carries the tally -- out, died, still inside --
and it adds up, which the spike's printed report did not. Space plays again from
a clean start.

**The room is shown once, at the start.** A flash of the whole layout, which
then fades over three seconds -- you cannot play a room you have never seen the
shape of, and what you keep is what you held in your head. It shows the building
and not who is in it.

**And the mains surge is the other one, and it is now built** (issue #53).
Every forty to seventy seconds the power surges and the whole building plan
appears -- both rooms, the doors, the people, the nests and the flies -- for a
second, with the game frozen while it is up. The two are deliberately different
things: the opening flash hands over one room's *layout*, the surge hands over
the whole building *and who is in it*. `--surge-frames N` changes how long it
lasts, because how long a surge has to be to be readable is a number that wants
finding at a keyboard.

**There are seven people in the room and you have to find them.** They are
bleeding from the frame the level starts, so a search is a race. Touch one to
free them and they follow; the exit banks whoever is behind you.

**The light bargain is live.** Clegs steer for the nearest lit source, so
switching the spotlight on brings them and switching it off loses them. They
attach, drain a bar of blood each, and drop off sated; the spray kills any that
is not already on you.

Turn the sound up. Clegs are only drawn where a light is on them, so in the dark
the sonar is the only thing that tells you they are coming: slow clicks are a
rumour, a fast rattle is a problem already on top of you.

The run itself lives in `session.py`, not here. This file is the host: a window,
a keyboard, a speaker and a clock. Everything it drives is portable, and the
headless driver in `spike_driver.py` drives exactly the same session with the
same constants -- which is the point of the split.
"""

import os
import sys

# Before pygame is imported, and only if the caller has not said otherwise.
# Pygame greets stdout on import, and a tester starting the game should see an
# empty terminal: the game says everything it has to say on the screen, and a
# banner in the terminal invites them to look for the rest of it there.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from spotlight.core.constants import FRAME_RATE
from spotlight.core.screen import Screen
from spotlight.frontend.display import Display

from . import (
    lighting, session as session_mod, screens, sources, spike_sound, surge,
)
from .session import Intent, Session

#: How long the searchlight's wake lingers, in frames, cycled with M. The
#: beam's brightness is not on this list -- it reads lit whatever the wake is,
#: because level and memory are separate (issue #12).
WAKES = (lighting.CHARGE_SWEEP, 20, 40, 80)

#: Frames the searchlight takes per cell, cycled with S. Six crosses the room
#: in about four seconds; three was tried and played too fast to react to.
BEAM_SPEEDS = (6, 9, 12, 4)

#: (key, readout, delta) -- flags use a delta of 0 and toggle instead.
#: Blood, light, spray and the lit flag are all real readouts and are no longer
#: pushed about by hand; only lives and keys are still placeholders.
PANEL_KEYS = (
    (pygame.K_3, "lives", -1), (pygame.K_4, "lives", +1),
    (pygame.K_0, "keys", 0),
)

# --- the three states a session is in --------------------------------------

TITLE, PLAY, ENDED = "title", "play", "ended"


#: The command-line switch that unlocks the developer keys. Off by default, and
#: deliberately not mentioned on any screen a tester will see.
DEBUG_FLAG = "--debug"


class Debug:
    """The developer's keys: everything that is not one of the three controls.

    **Only reachable with `--debug` on the command line.** Without it this class
    is never built, so there is no key sequence that can get at it -- the point
    is not that a tester is asked not to press `F`, it is that pressing `F` does
    nothing. The keys below sit on ordinary letters and a tester who fidgets
    used to be able to solve the game by accident and never know they had
    cheated.

    None of it is part of the game. It is here so the thing can be judged
    without rebuilding it -- watch the swarm decide where to go, try the
    searchlight at another speed, wipe the remembered light and see the room
    fresh:

        C  wipe the remembered light   R  force a strip repaint
        G  the personal glow           L  room lights
        N  the searchlight             W  do room lights show people?
        F  hold everything visible     Y  do workers call for help?
        U  bring the mains surge on now
        V  searchlight: vary <-> repeat
        B  searchlight: radius 3 <-> 4
        A  searchlight: knight's tour <-> straight rows
        S  searchlight: frames per cell
        I  searchlight: run to the wall <-> turn short of it
        M  searchlight: how long the wake lingers, in frames
        3/4  lives, still a placeholder    0  keys, still a placeholder

    `F` is the one that matters: it reveals the entire room and everybody in it
    and holds it there. **It is not a surge**: a surge is the building plan for
    a second with the game frozen, and this is the room itself, at full
    brightness, for as long as you like. Neither lures anything, so the swarm
    behaves exactly as it would in the dark, in full view.

    `U` exists for one job: **settling how long a surge should last** (issue
    #53). `--surge-frames N` sets the length and a surge otherwise arrives once
    every forty to seventy seconds, so comparing five values by playing would
    take five minutes of waiting. It brings the next one forward and nothing
    else -- the schedule then carries on from where it fired, exactly as it
    would have if the seed had said so.

    The searchlight preferences reset when a run does. They are how you want to
    look at it today, not part of the run.
    """

    def __init__(self, run: Session) -> None:
        self.run = run
        self.beam_speed = BEAM_SPEEDS.index(run.roaming.step_every)
        self.wake = WAKES.index(run.roaming.memory)

    #: The searchlight keys act on **the building's** searchlight, which is
    #: room A's, whether or not the player is standing in room A. Room B
    #: authors none (issue #21), and a key that did nothing in half the
    #: building would read as broken. The lighting keys act on the room the
    #: player is in, because that is the one they can see.

    def handle(self, key: int, screen: Screen) -> bool:
        """Act on a debug key. Returns True if the key was one of ours."""
        run = self.run
        if key == pygame.K_r:
            run.panel.draw(screen, force=True)
        elif key == pygame.K_c:
            # Every room's, not only this one's: wiping the memory of a room
            # you can see and leaving the one next door warm is a debug key
            # that lies about what it did.
            for place in run.places:
                place.field.charge[:] = bytes(len(place.field.charge))
        elif key == pygame.K_g:
            run.glow.toggle()
        elif key == pygame.K_l:
            for light in run.room_lights:
                light.toggle()
        elif key == pygame.K_n:
            run.roaming.toggle()
        elif key == pygame.K_v:
            run.roaming.vary = not run.roaming.vary
            print("searchlight:", "varying" if run.roaming.vary else "repeating")
        elif key == pygame.K_b:
            # 3 <-> 4, not 3 <-> 2: the station grid the searchlight tours is
            # spaced for a beam of three, and a narrower one cannot reach
            # between the stations.
            run.roaming.reshape(radius=7 - run.roaming.radius)
            if run.roaming.inset:
                run.roaming.reshape(inset=run.roaming.radius)
            print(f"searchlight: radius {run.roaming.radius}")
        elif key == pygame.K_i:
            run.roaming.reshape(inset=0 if run.roaming.inset
                                else run.roaming.radius)
            print(f"searchlight: inset {run.roaming.inset}")
        elif key == pygame.K_y:
            run.calls_on = not run.calls_on
            print("workers call for help:", run.calls_on)
        elif key == pygame.K_s:
            self.beam_speed = (self.beam_speed + 1) % len(BEAM_SPEEDS)
            run.roaming.step_every = BEAM_SPEEDS[self.beam_speed]
            print(f"searchlight: {run.roaming.step_every} frames per cell")
        elif key == pygame.K_a:
            run.roaming.set_mode(
                sources.Roaming.SWEEP
                if run.roaming.mode == sources.Roaming.ARC
                else sources.Roaming.ARC)
            print("searchlight sweeps",
                  "a knight's tour" if run.roaming.mode == sources.Roaming.ARC
                  else "in straight rows")
        elif key == pygame.K_u:
            # Due now, rather than drawn now: the surge then arrives through
            # the ordinary path, so it is still held off if the player happens
            # to be mid-doorway and the freeze is still the shell's.
            run.surge.due = run.frame
        elif key == pygame.K_f:
            run.opening.hold(not run.opening.held)
            print("debug view:",
                  "everything shown" if run.opening.held else "off")
        elif key == pygame.K_w:
            for light in run.room_lights:
                light.reveals = not light.reveals
            print("room lights show people:",
                  run.room_lights[0].reveals if run.room_lights
                  else "(this room has none)")
        elif key == pygame.K_m:
            self.wake = (self.wake + 1) % len(WAKES)
            run.roaming.memory = WAKES[self.wake]
            print(f"searchlight wake: {run.roaming.memory} frames")
        else:
            for panel_key, name, delta in PANEL_KEYS:
                if key == panel_key:
                    current = run.panel.values[name]
                    run.panel.set(name, (not current) if delta == 0
                                  else current + delta)
                    return True
            return False
        return True


def _movement() -> tuple[int, int]:
    """The held keys, read fresh every frame.

    Input is read and acted on in the same frame. Nothing buffers, smooths or
    accelerates -- responsiveness is a requirement, not a nicety.
    """
    keys = pygame.key.get_pressed()
    return (keys[pygame.K_RIGHT] - keys[pygame.K_LEFT],
            keys[pygame.K_DOWN] - keys[pygame.K_UP])


class Shell:
    """Title, play, ending, again -- the states a window is in.

    Pulled out of `main` so that a test can press keys at it without opening a
    window or waiting fifty times a second for one. It knows about pygame's key
    numbers and nothing else about pygame: no surface, no event loop, no clock.

    Restarting builds a **new** `Session`. There is no reset path and there
    should not be one: a reset is a list of things somebody has to remember to
    clear, and the list is wrong the first time somebody adds a field.
    """

    def __init__(self, screen: Screen, speaker=None,
                 debug: bool = False,
                 surge_frames: int = surge.SURGE_FRAMES) -> None:
        self.screen = screen
        self.state = TITLE
        self.run: Session | None = None
        #: Built only when the developer keys are unlocked, so that with them
        #: locked there is nothing for a stray key to reach.
        self.debug: Debug | None = None
        self.debug_enabled = debug
        #: The host makes the noise; the game says what the noise is. **One
        #: speaker and one path to it** (issue #54): the sonar's click, a
        #: body's tick and the fourteen effects are arbitrated in
        #: `sounds.Voice` inside the session, and this hands whatever won to
        #: `spike_sound.Speaker`. It used to be two callbacks wired to the two
        #: clicking voices, which is what let the effects be silent for a whole
        #: slice without anything noticing.
        self.speaker = speaker
        self._torch = False
        self._spray = False
        #: Frames the shell is holding for, because a moment asked it to
        #: (issue #52). **The game is not stepped during them and the session
        #: never hears about them.** See `frame`.
        self.held = 0
        #: How long a surge lasts, which is the user's number and reaches the
        #: session from `--surge-frames`. Kept here because a restart builds a
        #: new `Session` and the setting belongs to the sitting rather than to
        #: the run.
        self.surge_frames = surge_frames
        #: Frames the building plan is on screen for (issue #53). **The same
        #: mechanism as `held` and deliberately not a second one**: frames in
        #: which the game is not stepped, owned by the shell, invisible to the
        #: session. See `frame`.
        self.surging = 0
        screens.draw_title(screen)

    # --- input --------------------------------------------------------------

    def key(self, key: int) -> bool:
        """Handle one key press. Returns False if the player wants out."""
        if key == pygame.K_ESCAPE:
            # Bound in every state, always. Quitting is not a game action, and
            # a window a tester cannot close is a bug.
            return False
        if self.state == TITLE:
            self.start()
        elif self.state == ENDED:
            if key == pygame.K_SPACE:
                self.start()
        elif key == pygame.K_t:
            self._torch = True
        elif key == pygame.K_SPACE:
            self._spray = True
        elif self.debug is not None:
            self.debug.handle(key, self.screen)
        # ...and otherwise nothing at all. An unbound key is ignored.
        return True

    # --- the run ------------------------------------------------------------

    def start(self) -> None:
        """Begin a fresh run. Nothing survives from the last one."""
        self.run = Session(surge_frames=self.surge_frames)
        self.debug = Debug(self.run) if self.debug_enabled else None
        self.state = PLAY
        self._torch = self._spray = False
        self.held = self.surging = 0

    def frame(self, dx: int = 0, dy: int = 0) -> None:
        """One frame of whatever state we are in.

        **A pause is frames in which the game is not stepped, and they are the
        shell's** (issue #52). Three moments ask for one -- a death and the two
        endings -- and the whole of honouring it is here: `held` counts down,
        `run.step` is not called, and the frame that was on screen stays on
        screen. Nothing about the run moves.

        That is not a tidiness preference, it is the constraint the slice was
        built under. If the *session* held instead, its frame counter would go
        on advancing through the pause, every event after it would be stamped
        with a different frame, and every run log in the project would move --
        which is exactly the guarantee this round is measured by. The headless
        driver honours no pause at all for the same reason: a hold there would
        mean the same `--frames` bought fewer stepped frames and the tail of
        every log would shift. On the target this is the same thing again: the
        main loop stops calling the game step and goes on servicing the
        interrupt.

        What it costs, said plainly: the ending screen's TIME TAKEN counts
        stepped frames, so a run's reported time is short of wall-clock by
        however long it paused. The alternative is a pause in the run log,
        which is a far larger price for a much smaller problem.

        **The mains surge freezes the game the same way** (issue #53), and
        that is why it is `self.surging` here rather than a flag that makes
        `step` do nothing: a second mechanism for *frames in which the game is
        not stepped* would be a second thing to keep in step with this one, and
        a flag inside the session would move every event log in the project for
        the reason above. The only difference is what is on screen while it
        holds -- a pause holds the frame the moment happened on, a surge holds
        the building plan drawn over it.
        """
        if self.surging:
            # **The surge's freeze, and it is the pause's own mechanism**
            # (issue #53). The plan is on screen and the game is not stepped,
            # so the building does not move while you read it -- a plan you
            # have to memorise while being bitten is not a memorisation beat.
            # Nothing is drawn during these frames because nothing changes:
            # they cost the port nothing at all, and the whole price of a
            # surge is the two whole-screen repaints either side of them.
            self.surging -= 1
            return
        if self.held:
            self.held -= 1
            if not self.held and self.run is not None \
                    and self.run.over is not None:
                # The ending screen is what the pause was holding *off*. Fifty
                # frames of the last play frame -- the flash of where you died
                # still running on it -- and then the screen that explains it.
                self.state = ENDED
                self.show_ending()
            return
        if self.state != PLAY:
            return
        self.run.step(Intent(dx=dx, dy=dy, torch=self._torch,
                             spray=self._spray))
        self._torch = self._spray = False
        if self.speaker is not None:
            # Every frame, and it does nothing on most of them: a click, a tick
            # and the frame an effect begins on are the only three things that
            # start a sound. See `spike_sound.Speaker.play`.
            self.speaker.play(self.run.voice)
        self.run.draw(self.screen)
        # Taken after the frame is drawn, so what the pause holds on screen is
        # the frame the moment happened on.
        self.held = self.run.moments.take_pause()
        if self.run.over is not None and not self.held:
            self.state = ENDED
            self.show_ending()
            return
        if self.held:
            # **A death and a surge on the same frame**: the death is the beat
            # that frame and the surge is still owed, so it is taken on the
            # first played frame after the hold. Deferred rather than dropped,
            # exactly like a surge that comes due mid-threshold -- and two
            # screens back to back would read as the game hanging twice.
            return
        # **Taken after the frame is drawn**, so the plan goes over the frame
        # the surge fired on and the frames above hold it there.
        owed = self.run.surge.take()
        if owed:
            self.run.draw_surge(self.screen)
            # **The frame the plan is drawn on is the first of the surge's
            # frames**, because it is already on screen, so the shell holds the
            # rest. That off-by-one is worth the sentence: `--surge-frames 1`
            # has to mean one frame of plan, or the user tuning the number is
            # tuning something other than what they are looking at.
            self.surging = owed - 1

    def show_ending(self) -> None:
        run = self.run
        screens.draw_ending(self.screen, session_mod.ENDING_TEXT[run.over],
                            run.rescued, run.lost, run.inside, run.total,
                            run.seconds)


#: The switch that lets a sitting settle `surge.SURGE_FRAMES` without a
#: rebuild. **This is what the issue owes somebody who has to find a number by
#: playing**: five values in one sitting rather than five edits, and the
#: constant stays the one place the default is written down.
SURGE_FLAG = "--surge-frames"


def surge_frames_from(argv: list[str]) -> int:
    """`--surge-frames N`, or the default if it is not on the command line.

    A function rather than a line inside `main` so that a test can ask what a
    command line means without opening a window. It reads the switch and
    nothing else: what a length of 1 or 200 then does to a run is the shell's
    business and is tested there.
    """
    if SURGE_FLAG not in argv:
        return surge.SURGE_FRAMES
    return int(argv[argv.index(SURGE_FLAG) + 1])


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    scale = int(argv[argv.index("--scale") + 1]) if "--scale" in argv else 3
    surge_frames = surge_frames_from(argv)
    debug = DEBUG_FLAG in argv

    pygame.init()
    try:
        display = Display(scale=scale, title="Spotlight")
        clock = pygame.time.Clock()
        screen = Screen()
        speaker = spike_sound.Speaker()
        speaker.open()
        shell = Shell(screen, speaker=speaker,
                      debug=debug, surge_frames=surge_frames)

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = shell.key(event.key)

            shell.frame(*_movement())
            display.render(screen)
            # The Spectrum gets one 50Hz interrupt; match its frame budget.
            clock.tick(FRAME_RATE)
    finally:
        speaker.close()
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
