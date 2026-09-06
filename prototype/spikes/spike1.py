"""Spike 1 harness: screen regions and the status strip.

Run from the prototype directory:

    python -m spikes.spike1            # --scale N to resize

Debug keys change the placeholder readouts so the strip can be judged:

    1/2  blood down/up        7    toggle spotlight lit
    3/4  lives down/up        8/9  spray down/up
    5/6  light down/up        0    toggle key held
    R    force a full repaint  M   toggle the region-separation marker
    ESC  quit

There is no game here. The strip carries placeholder values only.
"""

import sys

import pygame

from spotlight.core.constants import BLACK, COLS, FRAME_RATE, WHITE
from spotlight.core.screen import Screen, attr_byte
from spotlight.frontend.display import Display

from .layout import PLAY_BOTTOM, PLAY_ROWS, PLAY_TOP
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

        marker_on, marker_x, repaints = True, 0, 0
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
                    for key, name, delta in BINDINGS:
                        if event.key != key:
                            continue
                        current = panel.values[name]
                        panel.set(name, (not current) if delta == 0
                                  else current + delta)

            # The play area is cleared every frame; the strip is not touched.
            screen.clear_rows(PLAY_TOP, PLAY_BOTTOM, PLAY_ATTR)
            if marker_on:
                # Proves the two regions repaint independently.
                marker_x = (marker_x + 1) % COLS
                screen.fill_cell_pixels(marker_x, PLAY_ROWS // 2, on=True)
                screen.set_attr(marker_x, PLAY_ROWS // 2, PLAY_ATTR)

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
