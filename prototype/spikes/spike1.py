"""The game, in a window: title screen, a room to search, an ending, and again.

Run it with:

    python -m spotlight            # --scale N to resize the window

**The game is four directions and two buttons.** That is the whole control
scheme and it is all a player ever touches:

    arrows   walk, and set your facing
    T        your carried spotlight, on and off
    SPACE    fire the flyspray ahead of you

    ESC      quit, from anywhere

**Everything else is inert unless the game is started with `--debug`.** There
are sixteen developer keys on ordinary letters and one of them, `F`, reveals the
entire room and everybody in it and holds it there. A tester who presses a key
to find out what it does could silently destroy the run we are asking them
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
and not who is in it. In the game proper this moment is the **mains surge**: the
same thing for a quarter of a second.

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

from . import lighting, session as session_mod, screens, sources, spike_buzz
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
    nothing. The sixteen keys below sit on ordinary letters and a tester who
    fidgets used to be able to solve the game by accident and never know they
    had cheated.

    None of it is part of the game. It is here so the thing can be judged
    without rebuilding it -- watch the swarm decide where to go, try the
    searchlight at another speed, wipe the remembered light and see the room
    fresh:

        C  wipe the remembered light   R  force a strip repaint
        G  the personal glow           L  room lights
        N  the searchlight             W  do room lights show people?
        F  hold everything visible     Y  do workers call for help?
        V  searchlight: vary <-> repeat
        B  searchlight: radius 3 <-> 4
        A  searchlight: knight's tour <-> straight rows
        S  searchlight: frames per cell
        I  searchlight: run to the wall <-> turn short of it
        M  searchlight: how long the wake lingers, in frames
        H  light hue: off -> on, memory keeps it -> on, memory reverts
        3/4  lives, still a placeholder    0  keys, still a placeholder

    `F` is the one that matters: it reveals the entire room and everybody in it
    and holds it there. It is not a surge -- a quarter of a second is too short
    to watch anything happen in -- and it lures nobody, so the swarm behaves
    exactly as it would in the dark, in full view.

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
        elif key == pygame.K_h:
            # off -> on with memory -> on without -> off
            field = run.field
            if not field.light_hue:
                field.light_hue, field.hue_memory = True, True
            elif field.hue_memory:
                field.hue_memory = False
            else:
                field.light_hue = False
            print("light hue:",
                  "off" if not field.light_hue else
                  "on, memory keeps it" if field.hue_memory else
                  "on, memory reverts")
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

    def __init__(self, screen: Screen, on_click=None,
                 debug: bool = False) -> None:
        self.screen = screen
        self.state = TITLE
        self.run: Session | None = None
        #: Built only when the developer keys are unlocked, so that with them
        #: locked there is nothing for a stray key to reach.
        self.debug: Debug | None = None
        self.debug_enabled = debug
        #: The host makes the noise; the session only says when.
        self.on_click = on_click
        self._torch = False
        self._spray = False
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
        self.run = Session()
        self.debug = Debug(self.run) if self.debug_enabled else None
        self.state = PLAY
        self._torch = self._spray = False

    def frame(self, dx: int = 0, dy: int = 0) -> None:
        """One frame of whatever state we are in."""
        if self.state != PLAY:
            return
        self.run.step(Intent(dx=dx, dy=dy, torch=self._torch,
                             spray=self._spray))
        self._torch = self._spray = False
        if self.run.click and self.on_click is not None:
            self.on_click()
        self.run.draw(self.screen)
        if self.run.over is not None:
            self.state = ENDED
            self.show_ending()

    def show_ending(self) -> None:
        run = self.run
        screens.draw_ending(self.screen, session_mod.ENDING_TEXT[run.over],
                            run.rescued, run.lost, run.inside, run.total,
                            run.seconds)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    scale = int(argv[argv.index("--scale") + 1]) if "--scale" in argv else 3
    debug = DEBUG_FLAG in argv

    pygame.init()
    try:
        display = Display(scale=scale, title="Spotlight")
        clock = pygame.time.Clock()
        screen = Screen()
        speaker = spike_buzz.Speaker()
        speaker.open()
        shell = Shell(screen, on_click=speaker.click, debug=debug)

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
