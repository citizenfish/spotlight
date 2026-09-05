"""Entry point: ``python -m spotlight`` from the prototype/ directory."""

import sys

import pygame

from .core.constants import FRAME_RATE
from .core.game import Game
from .core.screen import Screen
from .frontend import input as game_input
from .frontend.display import Display


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    scale = 3
    if "--scale" in argv:
        scale = int(argv[argv.index("--scale") + 1])

    pygame.init()
    try:
        display = Display(scale=scale)
        clock = pygame.time.Clock()
        screen = Screen()
        game = Game()

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False

            actions = game_input.poll()
            dx = bool(actions & game_input.Action.RIGHT) - bool(
                actions & game_input.Action.LEFT
            )
            dy = bool(actions & game_input.Action.DOWN) - bool(
                actions & game_input.Action.UP
            )
            game.update(dx, dy)
            game.draw(screen)
            display.render(screen)

            # The Spectrum gets one 50Hz interrupt; match its frame budget.
            clock.tick(FRAME_RATE)
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
