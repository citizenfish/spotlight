"""Keyboard handling, reduced to abstract actions.

The core never sees a key code. It sees an Action set, which the Z80 port can
fill just as easily from a half-row keyboard scan.
"""

from enum import Flag, auto

import pygame


class Action(Flag):
    NONE = 0
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    FIRE = auto()


#: QAOP + space -- the Spectrum default, and still the port's likely mapping.
KEY_MAP = {
    pygame.K_q: Action.UP,
    pygame.K_a: Action.DOWN,
    pygame.K_o: Action.LEFT,
    pygame.K_p: Action.RIGHT,
    pygame.K_SPACE: Action.FIRE,
    # Arrow keys as a modern convenience; the port will not have these.
    pygame.K_UP: Action.UP,
    pygame.K_DOWN: Action.DOWN,
    pygame.K_LEFT: Action.LEFT,
    pygame.K_RIGHT: Action.RIGHT,
}


def poll() -> Action:
    """Current held actions, read from the keyboard state."""
    pressed = pygame.key.get_pressed()
    actions = Action.NONE
    for key, action in KEY_MAP.items():
        if pressed[key]:
            actions |= action
    return actions
