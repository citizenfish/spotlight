"""Portable game logic.

Nothing here may import pygame, or any other host library. Everything in this
package has to have a plausible Z80 equivalent: integers, fixed point, and the
32x24 attribute grid. ``prototype/tests/test_portability.py`` enforces the
import rule.
"""
