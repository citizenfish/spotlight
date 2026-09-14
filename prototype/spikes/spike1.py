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
are fourteen developer keys on ordinary letters and one of them, `F`, reveals
the entire room and everybody in it and holds it there. A tester who presses a
key to find out what it does could silently destroy the run we are asking them
about and never know they had. They are all still there and they all still
work; they are simply not reachable by accident. See `Debug`.

Those three are now **named on the title screen**, in words, because they used
to be named only here: the window opened straight into the game and a
stranger had no way to learn that `T` existed at all. `T` is the bargain the
whole design rests on, so a player who does not know about it is not playing the
game. See `screens.py` for the wording and why it is worded that way.

A run has three endings and the screen says which: everyone out, nobody left to
save, or the last try gone. It carries the tally -- out, died, still inside --
and it adds up, which the spike's printed report did not. Space plays again from
a clean start.

**`S` starts a run from the title, and nothing else does** (issue #63). It was
any key, and any key is what a tester leaning on the keyboard or pressing `T`
while still reading the controls triggers by accident. `S` is also a debug key
in play -- the searchlight's speed -- and stays one: the title branch in
`Shell.key` is taken before the debug keys are read, so the two never meet.

**No room is ever shown whole, and no plan of the building is ever shown**
(issue #79). Until 2026-09-14 a room flashed up in full for twelve frames on
first entry, and once a minute the mains surged and the whole building plan
sat on a frozen game for a second. The user played both and ruled them out:
*"it will make the game more playable"*. What you see of a room is what your
own light and the room's own lights show you, and what the fade remembers.

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
from spotlight.frontend import display as display_mod
from spotlight.frontend.display import Display

from . import (
    lighting, session as session_mod, screens, sounds, sources, spike_sound,
    tune,
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
        V  searchlight: vary <-> repeat
        B  searchlight: radius 3 <-> 4
        A  searchlight: knight's tour <-> straight rows
        S  searchlight: frames per cell   (also starts a run from the title,
                                           where it is read first; #63)
        I  searchlight: run to the wall <-> turn short of it
        M  searchlight: how long the wake lingers, in frames
        3/4  lives, still a placeholder    0  keys, still a placeholder

    `F` is the one that matters: it reveals the entire room and everybody in it
    and holds it there -- the room itself, at full brightness, for as long as
    you like, and since issue #79 the only whole-room view there is. It lures
    nothing, so the swarm behaves exactly as it would in the dark, in full
    view -- **and since issue #64 that is true**: the held view set the one
    reveal-and-prey bit, so everybody under it was prey to any fly nearby and
    the swarm was not doing what it would have done in the dark. It now
    reveals without prey. See `sources.Floodlight.hold`.

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
            run.floodlight.hold(not run.floodlight.held)
            print("debug view:",
                  "everything shown" if run.floodlight.held else "off")
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


#: How long every level opens for, in frames (issue #81): two seconds, the
#: user's number, in which the first frame is held and the opening tune
#: plays. One bar of the tune is 96 of them; the last four are the breath
#: before play.
OPENING_FRAMES = 100


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
                 opening_frames: int = OPENING_FRAMES) -> None:
        self.screen = screen
        self.state = TITLE
        self.run: Session | None = None
        #: How long every level opens for (issue #81): frames the first
        #: picture is held and the opening tune plays before anything steps.
        #: A parameter so a test that wants play at once can ask for none;
        #: the game asks for `OPENING_FRAMES`.
        self.opening_frames = opening_frames
        #: Frames of the opening still to hold. Counted down in `frame` on
        #: the pause's mechanism and not a second one.
        self.opening = 0
        #: The opening tune's own voice, arbitrated like the title theme's
        #: for the same reason: one speaker and one path to it. Nothing else
        #: can raise a sound on a frame the run is not stepped.
        self.opening_voice = sounds.Voice(tune.Music(tune.OPENING))
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
        #: mechanism as `held` and deliberately not a second one**: frames in
        #: which the game is not stepped, owned by the shell, invisible to the
        #: session. See `frame`.
        self.surging = 0
        #: **The theme plays on the title screen and nowhere else** (issue
        #: #55, and untouched by #67, which put a siren under the run). The
        #: siren belongs to the run and is inside the session; the ending
        #: screen is silence and a count, and it stays that way. The title
        #: has no Clegs on it, so the theme is heard at the only load this
        #: game ever gives it: none. **The theme stays here on purpose**: a
        #: wail and twelve seconds of silence under a menu says the machine is
        #: idle, where the theme says a game is waiting.
        #:
        #: It is arbitrated by a `Voice` of its own rather than played
        #: directly, because *music is the bottom of the arbitration order* and
        #: a second path to the speaker is the drift that let the effects be
        #: silent for a whole slice without anybody noticing. Nothing else ever
        #: raises a sound on the title screen, so the voice has nothing to do
        #: but hand the frame to the music -- which is the point: it is the
        #: same rule, not a special case.
        self.title_voice = sounds.Voice(tune.Music(tune.THEME))
        screens.draw_title(screen)

    # --- input --------------------------------------------------------------

    def key(self, key: int) -> bool:
        """Handle one key press. Returns False if the player wants out."""
        if key == pygame.K_ESCAPE:
            # Bound in every state, always. Quitting is not a game action, and
            # a window a tester cannot close is a bug.
            return False
        if self.state == TITLE:
            # **`S` and only `S`** (issue #63). Any key used to start a run,
            # which is what a tester reading the controls and trying `T`
            # triggered by accident. This branch comes before the debug keys
            # on purpose: `S` is the searchlight-speed key in play, and the
            # two never collide because a title has no run for it to act on.
            if key == pygame.K_s:
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
        """Begin a fresh run. Nothing survives from the last one.

        **Every level opens on a two-second hold and a tune** (issue #81):
        the run's first frame is stepped and drawn -- the first picture a
        player sees, where they are standing by their own glow and the room's
        own lights -- and then held for `opening_frames` frames while the
        opening plays and nothing steps, so the player can take it in before
        anything can happen to them. The same on a restart from the ending
        screen, and on every level when there are levels. The hold is the
        shell's, on the pause's mechanism; the session never hears of it and
        the log cannot move.
        """
        self.run = Session()
        self.debug = Debug(self.run) if self.debug_enabled else None
        self.state = PLAY
        self._torch = self._spray = False
        self.held = 0
        # The theme stops where it stops. It is not faded out and it is not
        # resumed: the next title screen starts it again from bar one, because
        # a title screen is a beginning.
        self.title_voice.music.play(tune.THEME)
        self.run.step(Intent())
        self.run.draw(self.screen)
        self.opening = self.opening_frames
        self.opening_voice.music.play(tune.OPENING)

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

        The mains surge froze the game the same way, on this mechanism and
        not a second one, until issue #79 removed it.
        """
        if self.held:
            self.held -= 1
            self._sound_frame()
            if not self.held and self.run is not None \
                    and self.run.over is not None:
                # The ending screen is what the pause was holding *off*. Fifty
                # frames of the last play frame -- the flash of where you died
                # still running on it -- and then the screen that explains it.
                self.state = ENDED
                self.show_ending()
            return
        if self.state == TITLE:
            # The theme, on the one screen it plays on. Nothing is raised
            # here, so every frame of it is a frame the music is given.
            self.title_voice.update(False, False)
            if self.speaker is not None:
                self.speaker.play(self.title_voice)
            return
        if self.state != PLAY:
            # The ending screen: no tune, no click, nothing. Silence and a
            # count is what the design asks for and what it keeps.
            return
        if self.opening:
            # **The level's opening** (issue #81): the first frame held, the
            # opening tune on the speaker, and the run not stepped. The run's
            # own voice is not touched either: nothing in it has started --
            # the first frame raises no sound and the siren has not begun --
            # so its clock starts when play does, and the siren's first wail
            # rises from the first stepped frame. Keys pressed now land on
            # that frame, as they do during a pause.
            self.opening -= 1
            self.opening_voice.update(False, False)
            if self.speaker is not None:
                self.speaker.play(self.opening_voice)
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

    def _sound_frame(self) -> None:
        """A frame the sound player ran and the game did not (issue #57).

        **The effect clock belongs to the interrupt, not to the game step.**
        On the target the player routine is driven by the 50Hz interrupt and
        does not care that the game logic is paused; here the shell holds
        frames for a moment's pause, and during them nothing
        was ageing the sound. The mixer was playing it all the same, because
        the host is handed a whole effect at once, so the arbiter went on
        guarding a sound that had already finished -- 25 frames of it after a
        player's death, measured through this shell, with the sonar dropped
        throughout. See `sounds.Voice.audio_frame`.

        The speaker is asked as well as the clock, for the one case where a
        click punctured the effect on the frame before the hold began: the
        channel is playing the click, and the effect has to be picked up again
        part-way or its tail is lost. Costs nothing on any other frame.
        """
        if self.run is None or self.run.voice is None:
            return
        self.run.voice.audio_frame()
        if self.speaker is not None:
            self.speaker.play(self.run.voice)

    def show_ending(self) -> None:
        run = self.run
        screens.draw_ending(self.screen, session_mod.ENDING_TEXT[run.over],
                            run.rescued, run.lost, run.inside, run.total,
                            run.seconds)


#: `--border COLOUR` (issue #75): the Spectrum's BORDER, as a margin round the
#: window in one of its fifteen colours. It exists so the user can try in a
#: minute whether a dark room inside a frame of colour reads as a room; it
#: reaches the window and nothing else -- no rule reads it and no snapshot
#: shows it, because a snapshot is the 256x192 and the border is outside it.
BORDER_FLAG = "--border"


def border_from(argv: list[str]) -> str:
    """The border colour's name, or the default if it is not asked for.

    The name is checked here, before any window opens, so that a mistyped
    colour is one line on stderr and not a window with a traceback behind it.
    """
    if BORDER_FLAG not in argv:
        return display_mod.DEFAULT_BORDER
    name = argv[argv.index(BORDER_FLAG) + 1]
    display_mod.border_colour(name)      # raises ValueError, naming the set
    return name


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    scale = int(argv[argv.index("--scale") + 1]) if "--scale" in argv else 3
    debug = DEBUG_FLAG in argv
    try:
        border = border_from(argv)
    except ValueError as err:
        print(err, file=sys.stderr)
        return 2

    pygame.init()
    try:
        display = Display(scale=scale, title="Spotlight", border=border)
        clock = pygame.time.Clock()
        screen = Screen()
        speaker = spike_sound.Speaker()
        speaker.open()
        shell = Shell(screen, speaker=speaker, debug=debug)

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
