"""Spike 1 harness: screen regions, the status strip, and the lighting model.

Run from the prototype directory:

    python -m spikes.spike1            # --scale N to resize

Debug keys change the placeholder readouts so the strip can be judged:

    arrows  walk, and set facing      G  toggle the personal glow
    T       toggle the cone           L  toggle the room light
    C       clear the light field     N  toggle the searchlight
    R       force a strip repaint     V  searchlight: repeat <-> vary
    SPACE   fire the flyspray         T  toggle the carried spotlight
    ESC     quit                      1-0  placeholder strip readouts

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
from .panel import Panel, blank_strip

PLAY_ATTR = attr_byte(ink=WHITE, paper=BLACK, bright=False)

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
        room_lights = [sources.RoomLight(*z) for z in scene.light_zones()]
        room = room_lights[0]
        cone = sources.Cone(reach=7)
        cone.x, cone.y, cone.facing = player.cx, player.cy, player.facing
        kit = Spotlights(cone, [FloorLight(cx, cy, power)
                                for cx, cy, power in scene.SPOTLIGHTS])
        spray = spray_mod.Spray(charges=5)
        # A prison searchlight quartering the room. One circuit covers
        # everywhere; V switches between repeating and varying.
        roaming = sources.Roaming(0, 0, radius=3, step_every=3)
        all_sources = (glow, cone, roaming, *room_lights)
        cone_full = max(p for _, _, p in scene.SPOTLIGHTS)

        scenery = [(sprites.SPRITES[name], x, y)
                   for name, x, y in scene.ENTITIES]
        for cx, cy in scene.cells_of(scene.KEY):
            scenery.append((sprites.KEY, cx * CELL, cy * CELL))

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
            panel.set("light", cone.power * 6 // max(1, cone_full))
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
            for spr, sx, sy in scenery:
                sprites.draw(screen, spr, sx, sy)
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
