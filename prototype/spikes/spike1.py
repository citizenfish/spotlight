"""Spike 1 harness: screen regions, the status strip, and the lighting model.

Run from the prototype directory:

    python -m spikes.spike1            # --scale N to resize

Debug keys change the placeholder readouts so the strip can be judged:

    arrows  move the test light      1/2  blood down/up
    SPACE   hold to light a cell      3/4  lives down/up
    D       drop a dim source         5/6  light down/up
    C       clear the light field     7    toggle spotlight lit
    R       force a strip repaint     8/9  spray down/up
    M       toggle the marker         0    toggle key held
    ESC     quit

There is no game here. The strip carries placeholder values, and the test light
exists only so the fade can be watched decaying LIT -> DIM -> DARK.
"""

import sys

import pygame

from spotlight.core.constants import BLACK, COLS, FRAME_RATE, WHITE, YELLOW
from spotlight.core.screen import Screen, attr_byte
from spotlight.frontend.display import Display

from . import lighting
from .layout import PLAY_BOTTOM, PLAY_ROWS, PLAY_TOP
from .lighting import LightField
from .panel import Panel, blank_strip

PLAY_ATTR = attr_byte(ink=WHITE, paper=BLACK, bright=False)

#: Ink the play area wears. Light decides the level; this decides the hue.
PLAY_INK = YELLOW

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
        light_x, light_y = COLS // 2, PLAY_ROWS // 2
        marker_on, marker_x, repaints = False, 0, 0
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
                    elif event.key == pygame.K_m:
                        marker_on = not marker_on
                    elif event.key == pygame.K_c:
                        field.charge[:] = bytes(len(field.charge))
                    for key, name, delta in BINDINGS:
                        if event.key != key:
                            continue
                        current = panel.values[name]
                        panel.set(name, (not current) if delta == 0
                                  else current + delta)

            keys = pygame.key.get_pressed()
            light_x = max(0, min(COLS - 1, light_x
                                 + keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]))
            light_y = max(0, min(PLAY_ROWS - 1, light_y
                                 + keys[pygame.K_DOWN] - keys[pygame.K_UP]))

            # Lighting: sources contribute, brightest wins, then everything
            # decays by a frame.
            field.begin()
            if keys[pygame.K_SPACE]:
                field.add(light_x, light_y, lighting.LIT)
            if keys[pygame.K_d]:
                field.add(light_x, light_y, lighting.DIM)
            field.commit()

            # The play area is cleared every frame; the strip is not touched.
            screen.clear_rows(PLAY_TOP, PLAY_BOTTOM, PLAY_ATTR)
            for cy in range(PLAY_ROWS):
                for cx in range(COLS):
                    if field.level_at(cx, cy):
                        screen.fill_cell_pixels(cx, cy, on=True)
            if marker_on:
                marker_x = (marker_x + 1) % COLS
                screen.fill_cell_pixels(marker_x, PLAY_ROWS // 2, on=True)

            # Light decides colour, and nothing else does. This overwrites
            # every play-area attribute, so it must come after the drawing.
            field.paint(screen, PLAY_INK)

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
