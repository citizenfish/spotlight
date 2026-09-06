"""Spike 1 harness: screen regions, the status strip, and the lighting model.

Run from the prototype directory:

    python -m spikes.spike1            # --scale N to resize

Debug keys change the placeholder readouts so the strip can be judged:

    arrows  move, and set facing     G  toggle the personal glow
    T       toggle the cone           L  toggle the room light
    C       clear the light field     N  toggle the roaming spotlight
    R       force a strip repaint     P  roaming: drift <-> path
    ESC     quit                      1-0  placeholder strip readouts

There is no game here -- no collision, no AI. The four sources composite through
the lighting model, and sprites are drawn over the top by pixel, so the shapes,
the overlap, the fade behind a moving light and above all whether a two-toned
sprite reads can all be judged.
"""

import sys

import pygame

from spotlight.core.constants import BLACK, CELL, COLS, FRAME_RATE, WHITE
from spotlight.core.screen import Screen, attr_byte
from spotlight.frontend.display import Display

from . import lighting, scene, sources, sprites
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
        glow = sources.Glow()
        glow.x, glow.y = scene.PLAYER_START[0] // CELL, scene.PLAYER_START[1] // CELL
        scene.validate()
        inks = scene.ink_map()
        room_lights = [sources.RoomLight(*z) for z in scene.light_zones()]
        room = room_lights[0]
        cone = sources.Cone(reach=7)
        cone.x, cone.y, cone.facing = glow.x, glow.y, sources.RIGHT
        roaming = sources.Roaming(
            x=COLS - 6, y=PLAY_ROWS - 5, radius=3,
            path=[(COLS - 4, 3), (COLS - 4, PLAY_ROWS - 4),
                  (COLS - 20, PLAY_ROWS - 4), (COLS - 20, 3)],
        )
        roaming.set_mode(sources.Roaming.DRIFT)
        all_sources = (glow, cone, roaming, *room_lights)
        cone_full = cone.power

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
                        cone.toggle()
                    elif event.key == pygame.K_n:
                        roaming.toggle()
                    elif event.key == pygame.K_p:
                        roaming.set_mode(sources.Roaming.DRIFT
                                         if roaming.mode == sources.Roaming.PATH
                                         else sources.Roaming.PATH)
                    for key, name, delta in BINDINGS:
                        if event.key != key:
                            continue
                        current = panel.values[name]
                        panel.set(name, (not current) if delta == 0
                                  else current + delta)

            keys = pygame.key.get_pressed()
            dx = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
            dy = keys[pygame.K_DOWN] - keys[pygame.K_UP]
            if dx or dy:
                glow.x = max(0, min(COLS - 1, glow.x + dx))
                glow.y = max(0, min(PLAY_ROWS - 1, glow.y + dy))
                # Facing is the direction last moved; it aims the cone.
                if dx:
                    cone.facing = sources.RIGHT if dx > 0 else sources.LEFT
                else:
                    cone.facing = sources.DOWN if dy > 0 else sources.UP
            cone.x, cone.y = glow.x, glow.y

            roaming.update()
            cone.drain()
            panel.set("light", cone.power * 6 // max(1, cone_full))

            # Sources contribute, brightest wins, then everything decays.
            field.begin()
            for src in all_sources:
                src.apply(field)
            field.commit()

            # The play area is cleared every frame; the strip is not touched.
            screen.clear_rows(PLAY_TOP, PLAY_BOTTOM, PLAY_ATTR)

            for cy in range(PLAY_ROWS):
                for cx in range(COLS):
                    if scene.is_solid(cx, cy):
                        screen.fill_cell_pixels(cx, cy, on=True)

            # Sprites set pixels only. Their colour comes from whichever cells
            # they happen to be standing in.
            for spr, sx, sy in scenery:
                sprites.draw(screen, spr, sx, sy)
            sprites.draw(screen, sprites.PLAYER, glow.x * 8, glow.y * 8 - 8)

            # Light decides colour, and nothing else does. This overwrites
            # every play-area attribute, so it must come after the drawing.
            field.paint(screen, inks)

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
