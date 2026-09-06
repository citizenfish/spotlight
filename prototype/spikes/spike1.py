"""Spike 1 harness: screen regions, the status strip, and the lighting model.

Run from the prototype directory:

    python -m spikes.spike1            # --scale N to resize

**The game is four directions and two buttons.** That is the whole control
scheme and it is all a player ever touches:

    arrows   walk, and set your facing
    T        your carried spotlight, on and off
    SPACE    fire the flyspray ahead of you

Everything else is a debug key. None of it is part of the game; it is here so
the thing can be judged without rebuilding it:

    ESC   quit                        F  flash the room again
    C     wipe the remembered light   R  force a strip repaint
    G     the personal glow           L  room lights
    N     the searchlight             W  do room lights show people?
    V     searchlight: vary <-> repeat
    B     searchlight: radius 3 <-> 2
    I     searchlight: run to the wall <-> turn short of it
    M     searchlight: how long the wake lingers, in frames
    H     light hue: off -> on, memory keeps it -> on, memory reverts
    3/4   lives, still a placeholder   0  keys, still a placeholder

**The room is shown once, at the start.** A flash of the whole layout, which
then fades over three seconds -- you cannot play a room you have never seen the
shape of, and what you keep is what you held in your head. It shows the building
and not who is in it. F fires it again.

**The light bargain is now live.** Clegs steer for the nearest lit source, so
switching the spotlight on brings them and switching it off loses them. They
attach, drain a bar of blood each, and drop off sated; the spray kills any that
is not already on you. Blood, light and spray on the strip are real readouts.

Turn the sound up. Clegs are only drawn where a light is on them, so in the dark
the sonar is the only thing that tells you they are coming: slow clicks are a
rumour, a fast rattle is a problem already on top of you.

There is still no game here -- no doors, no workers, no quota. What there is is
one room in which the decision the whole design rests on can actually be made:
switch the light on to see, and be found because you did.
"""

import sys

import pygame

from spotlight.core.constants import BLACK, CELL, COLS, CYAN, FRAME_RATE, WHITE
from spotlight.core.screen import Screen, attr_byte
from spotlight.frontend.display import Display

from . import (
    buzz, clegs as clegs_mod, floor, lighting, scene, sources,
    spike_buzz, spray as spray_mod, sprites,
)
from .player import Player
from .spotlights import FloorLight, Spotlights
from .layout import PLAY_BOTTOM, PLAY_ROWS, PLAY_TOP
from .lighting import LightField
from .panel import Panel, bar_pips, blank_strip

PLAY_ATTR = attr_byte(ink=WHITE, paper=BLACK, bright=False)

#: How long the searchlight's wake lingers, in frames, cycled with M. The
#: beam's brightness is not on this list -- it reads lit whatever the wake is,
#: because level and memory are separate (issue #12).
WAKES = (lighting.CHARGE_SWEEP, 20, 40, 80)

#: Blood, as points. Shown as eight pips, so each pip is a Cleg's worth: one
#: attachment takes exactly one bar. A number small enough that the player can
#: count what a swarm cost them.
BLOOD_FULL = 64

#: (key, readout, delta) -- flags use a delta of 0 and toggle instead.
#: Blood, light, spray and the lit flag are all real readouts now and are no
#: longer pushed about by hand; only lives and keys are still placeholders.
BINDINGS = (
    (pygame.K_3, "lives", -1), (pygame.K_4, "lives", +1),
    (pygame.K_0, "keys", 0),
)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    scale = int(argv[argv.index("--scale") + 1]) if "--scale" in argv else 3

    pygame.init()
    try:
        display = Display(scale=scale, title="Spotlight - spike 1")
        clock = pygame.time.Clock()
        screen = Screen()
        panel = Panel()

        # The strip is painted once here and thereafter only where it changes.
        blank_strip(screen)
        panel.draw_labels(screen)
        for name, value in (("blood", 8), ("lives", 3), ("light", 4),
                            ("lit", 1), ("spray", 5), ("keys", 0)):
            panel.set(name, value)
        panel.draw(screen)

        field = LightField()
        player = Player(*scene.PLAYER_START)
        glow = sources.Glow()
        glow.x, glow.y = player.cx, player.cy
        scene.validate()
        inks = scene.ink_map()
        # This room authors none, but the source and the L key stay, so a
        # zone can be put back into `scene.ROOM` and looked at.
        room_lights = [sources.RoomLight(*z) for z in scene.light_zones()]
        cone = sources.Cone(reach=7)
        cone.x, cone.y, cone.facing = player.cx, player.cy, player.facing
        kit = Spotlights(cone, [FloorLight(cx, cy, power)
                                for cx, cy, power in scene.SPOTLIGHTS])
        spray = spray_mod.Spray(charges=5)
        swarm = clegs_mod.Swarm([clegs_mod.Cleg(cx, cy, seed=0xBEEF + i)
                                 for i, (cx, cy) in enumerate(scene.CLEGS)])
        blood = BLOOD_FULL
        sonar = buzz.Sonar()
        speaker = spike_buzz.Speaker()
        speaker.open()
        # The room is shown once, at the start, and then taken away. What the
        # player keeps is what they held in their head.
        opening = sources.Flash()
        opening.fire()
        # A prison searchlight quartering the room. One circuit covers
        # everywhere. It starts **varying** -- a different route each circuit,
        # so it cannot be planned around -- and runs to the wall rather than
        # turning short of it. Both settled by playing; V and I switch them.
        roaming = sources.Roaming(0, 0, radius=3, step_every=3, vary=True)
        wake = WAKES.index(roaming.memory)
        all_sources = (glow, cone, roaming, opening, *room_lights)
        cone_full = max(p for _, _, p in scene.SPOTLIGHTS)

        # The building is remembered; its inhabitants are not. Fixtures stay
        # drawn in remembered ground, because they will still be there. People
        # and Clegs are drawn only where a light is on them right now.
        fixtures = [(sprites.SPRITES[name], x, y)
                    for name, x, y in scene.ENTITIES
                    if name not in scene.MOVERS]
        movers = [(sprites.SPRITES[name], x, y)
                  for name, x, y in scene.ENTITIES if name in scene.MOVERS]
        for cx, cy in scene.cells_of(scene.KEY):
            fixtures.append((sprites.KEY, cx * CELL, cy * CELL))

        repaints = 0
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_r:
                        panel.draw(screen, force=True)
                    elif event.key == pygame.K_c:
                        field.charge[:] = bytes(len(field.charge))
                    elif event.key == pygame.K_g:
                        glow.toggle()
                    elif event.key == pygame.K_l:
                        for rl in room_lights:
                            rl.toggle()
                    elif event.key == pygame.K_t:
                        kit.toggle()
                    elif event.key == pygame.K_n:
                        roaming.toggle()
                    elif event.key == pygame.K_SPACE:
                        if spray.fire(player.cx, player.cy, player.facing):
                            panel.set("spray", spray.charges)
                    elif event.key == pygame.K_v:
                        roaming.vary = not roaming.vary
                        print("searchlight:",
                              "varying" if roaming.vary else "repeating")
                    elif event.key == pygame.K_b:
                        roaming.reshape(radius=5 - roaming.radius)  # 3 <-> 2
                        if roaming.inset:
                            roaming.reshape(inset=roaming.radius)
                        print(f"searchlight: radius {roaming.radius}")
                    elif event.key == pygame.K_i:
                        roaming.reshape(
                            inset=0 if roaming.inset else roaming.radius)
                        print(f"searchlight: inset {roaming.inset}")
                    elif event.key == pygame.K_f:
                        opening.fire()
                    elif event.key == pygame.K_w:
                        for rl in room_lights:
                            rl.reveals = not rl.reveals
                        print("room lights show people:",
                              room_lights[0].reveals if room_lights
                              else "(this room has none)")
                    elif event.key == pygame.K_m:
                        wake = (wake + 1) % len(WAKES)
                        roaming.memory = WAKES[wake]
                        print(f"searchlight wake: {roaming.memory} frames "
                              f"({roaming.memory / FRAME_RATE:.1f}s)")
                    elif event.key == pygame.K_h:
                        # off -> on with memory -> on without -> off
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
                    for key, name, delta in BINDINGS:
                        if event.key != key:
                            continue
                        current = panel.values[name]
                        panel.set(name, (not current) if delta == 0
                                  else current + delta)

            # Input is read and acted on in the same frame. Nothing buffers,
            # smooths or accelerates -- responsiveness is a requirement.
            keys = pygame.key.get_pressed()
            player.move(keys[pygame.K_RIGHT] - keys[pygame.K_LEFT],
                        keys[pygame.K_DOWN] - keys[pygame.K_UP],
                        scene.is_solid)
            glow.x, glow.y = player.cx, player.cy
            cone.x, cone.y, cone.facing = player.cx, player.cy, player.facing

            roaming.update()
            opening.update()
            spray.tick()

            # The one rule: Clegs steer for the nearest light that is actually
            # lit. The glow is dim and so pulls nothing, which is what makes
            # walking in the dark safe and the toggle a decision.
            lures = [p for p in (s.lure() for s in all_sources) if p is not None]
            lures += kit.floor_lures()
            was_attached = len(swarm.attached())
            blood = swarm.tick(lures, (player.cx, player.cy), scene.is_solid,
                               blood)
            # Spray reaches everything except a Cleg already on you.
            killed = swarm.kill(spray.kills(swarm.sprayable()))
            if killed:
                print(f"spray killed {killed}; {len(swarm.clegs)} left")
            if len(swarm.attached()) != was_attached:
                print(f"attached: {len(swarm.attached())}  blood {blood}")
            picked = kit.tick(player)
            if picked is not None:
                print(f"swapped: carrying {cone.power}, left "
                      f"{'burning' if picked.burning else 'dark'} light at "
                      f"({picked.cx}, {picked.cy})")
            panel.set("light", bar_pips(cone.power, cone_full))
            panel.set("lit", cone.lit)
            panel.set("blood", bar_pips(blood, BLOOD_FULL, 8))
            # You hear them before you see them -- and since a Cleg is only
            # drawn where a light is on it, in the dark this is all you get.
            # Clicks rather than a tone: a rate carries urgency, a drone does
            # not, and a click is the cheapest noise the target can make.
            if sonar.update(swarm.nearest_distance(player.cx, player.cy)):
                speaker.click()

            # Sources contribute, brightest wins, then everything decays.
            field.begin()
            for src in all_sources:
                src.apply(field)
            kit.apply(field)
            field.commit()

            # The play area is cleared every frame; the strip is not touched.
            screen.clear_rows(PLAY_TOP, PLAY_BOTTOM, PLAY_ATTR)

            for cy in range(PLAY_ROWS):
                for cx in range(COLS):
                    if scene.is_solid(cx, cy):
                        screen.fill_cell_pixels(cx, cy, on=True)

            # Lit floor is stippled, denser when fully lit. Without this the
            # light has no visible shape -- it only reveals what it falls on.
            floor.draw(screen, field, scene.is_solid)

            # Sprites set pixels only. Their colour comes from whichever cells
            # they happen to be standing in.
            for spr, sx, sy in fixtures:
                sprites.draw(screen, spr, sx, sy)
            for spr, sx, sy in movers:
                sprites.draw(screen, spr, sx, sy, visible=field.reveals_at)
            for cleg in swarm.clegs:
                sprites.draw(screen, sprites.CLEG, cleg.cx * CELL,
                             cleg.cy * CELL, visible=field.reveals_at)
            sprites.draw(screen, sprites.PLAYER, player.x, player.y)

            # Sprayed ground gets its own droplet pattern and its own hue.
            # Hue is per-cell, so this does not disturb the clash guarantee.
            frame_inks = bytearray(inks)
            for cx, cy in spray.patches:
                for dy, bits in enumerate(spray_mod.STIPPLE):
                    for dx in range(CELL):
                        if bits & (0x80 >> dx):
                            screen.plot(cx * CELL + dx, cy * CELL + dy)
                frame_inks[cy * COLS + cx] = CYAN

            # Light decides brightness, contents decide hue. This overwrites
            # every play-area attribute, so it must come after the drawing.
            field.paint(screen, frame_inks)

            touched = panel.draw(screen)
            if touched:
                repaints += 1
                print(f"strip repaint {repaints}: {len(touched)} cells -> "
                      f"{panel.values}")

            display.render(screen)
            clock.tick(FRAME_RATE)
    finally:
        speaker.close()
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
