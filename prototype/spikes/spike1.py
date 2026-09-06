"""Spike 1 harness: screen regions, the status strip, and the lighting model.

Run from the prototype directory:

    python -m spikes.spike1            # --scale N to resize

Debug keys change the placeholder readouts so the strip can be judged:

    arrows  walk, and set facing      G  toggle the personal glow
    T       toggle the cone           L  toggle the room light
    C       clear the light field     N  toggle the searchlight
    R       force a strip repaint     V  searchlight: repeat <-> vary
    SPACE   fire the flyspray         B  searchlight: beam radius 3 <-> 2
    ESC     quit                      I  searchlight: run to the wall <-> inset
    1-0     placeholder strip readouts
    H       light hue: off -> on, memory keeps it -> on, memory reverts
    M       how long the beam's wake lingers, in frames
    W       whether room lights show people, or only the room

The searchlight keys are the issue #12 knobs: a short bright memory and its
own hue, so the beam reads as a moving pool rather than a painted bar.

There is no game here -- no collision, no AI. The four sources composite through
the lighting model, and sprites are drawn over the top by pixel, so the shapes,
the overlap, the fade behind a moving light and above all whether a two-toned
sprite reads can all be judged.
"""

import sys

import pygame

from spotlight.core.constants import BLACK, CELL, COLS, CYAN, FRAME_RATE, WHITE
from spotlight.core.screen import Screen, attr_byte
from spotlight.frontend.display import Display

from . import floor, lighting, scene, sources, spray as spray_mod, sprites
from .player import Player
from .spotlights import FloorLight, Spotlights
from .layout import PLAY_BOTTOM, PLAY_ROWS, PLAY_TOP
from .lighting import LightField
from .panel import Panel, bar_pips, blank_strip

PLAY_ATTR = attr_byte(ink=WHITE, paper=BLACK, bright=False)

#: How long the searchlight's wake lingers, in frames, cycled with M. The
#: beam's brightness is not on this list -- it reads lit whatever the wake is,
#: because level and memory are separate (issue #12).
WAKES = (lighting.CHARGE_SWEEP, 10, 40, 80)

#: (key, readout, delta) -- flags use a delta of 0 and toggle instead.
BINDINGS = (
    (pygame.K_1, "blood", -1), (pygame.K_2, "blood", +1),
    (pygame.K_3, "lives", -1), (pygame.K_4, "lives", +1),
    (pygame.K_5, "light", -1), (pygame.K_6, "light", +1),
    (pygame.K_8, "spray", -1), (pygame.K_9, "spray", +1),
    (pygame.K_7, "lit", 0), (pygame.K_0, "keys", 0),
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
        # A prison searchlight quartering the room. One circuit covers
        # everywhere; V switches between repeating and varying.
        roaming = sources.Roaming(0, 0, radius=3, step_every=3)
        wake = WAKES.index(roaming.memory)
        all_sources = (glow, cone, roaming, *room_lights)
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
            spray.tick()
            picked = kit.tick(player)
            if picked is not None:
                print(f"swapped: carrying {cone.power}, left "
                      f"{'burning' if picked.burning else 'dark'} light at "
                      f"({picked.cx}, {picked.cy})")
            panel.set("light", bar_pips(cone.power, cone_full))
            panel.set("lit", cone.lit)

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
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
