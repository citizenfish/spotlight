"""Player movement, facing and collision."""

from spikes import scene, sources as S
from spikes.layout import PLAY_ROWS
from spikes.player import HEIGHT, SPEED, WIDTH, Player
from spotlight.core.constants import CELL, COLS


def _open():
    """A world with no walls at all, except outside the room."""
    return lambda cx, cy: not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS)


# --- movement --------------------------------------------------------------

def test_movement_is_by_pixel_not_by_cell():
    p = Player(100, 100)
    p.move(1, 0, _open())
    assert p.x == 100 + SPEED
    assert p.x % CELL != 0 or SPEED == CELL


def test_moving_reports_whether_anything_happened():
    p = Player(100, 100)
    assert p.move(1, 0, _open()) is True
    assert p.move(0, 0, _open()) is False


# --- facing ----------------------------------------------------------------

def test_facing_follows_the_direction_last_moved():
    p = Player(100, 100)
    for dx, dy, expected in ((1, 0, S.RIGHT), (-1, 0, S.LEFT),
                             (0, 1, S.DOWN), (0, -1, S.UP)):
        p.move(dx, dy, _open())
        assert p.facing == expected


def test_horizontal_facing_wins_on_a_diagonal():
    """Otherwise facing flickers between two values while moving diagonally."""
    p = Player(100, 100)
    p.move(1, 1, _open())
    assert p.facing == S.RIGHT


def test_facing_is_unchanged_when_standing_still():
    p = Player(100, 100)
    p.move(0, -1, _open())
    assert p.facing == S.UP
    p.move(0, 0, _open())
    assert p.facing == S.UP


def test_facing_changes_even_when_movement_is_blocked():
    """Turning to face a wall must work, or you cannot aim into a corner."""
    p = Player(*scene.PLAYER_START)
    for _ in range(400):
        p.move(-1, 0, scene.is_solid)          # jam against the west wall
    x_before = p.x
    assert p.move(-1, 0, scene.is_solid) is False
    assert p.facing == S.LEFT and p.x == x_before


# --- collision -------------------------------------------------------------

def test_the_player_cannot_walk_through_walls():
    p = Player(*scene.PLAYER_START)
    for _ in range(2000):
        p.move(1, 0, scene.is_solid)
        p.move(0, 1, scene.is_solid)
    for cx, cy in p.occupied_cells():
        assert not scene.is_solid(cx, cy), f"ended up inside a wall at {cx},{cy}"


def test_collision_uses_the_whole_sprite_box_not_one_cell():
    """A person is 8x16 and can be inside a wall with their head or their feet."""
    solid = lambda cx, cy: cy == 5
    p = Player(100, 6 * CELL - HEIGHT + 1)     # head would enter row 5
    assert p.move(0, -1, solid) is False


def test_walking_diagonally_into_a_wall_slides_along_it():
    """Stopping dead on a diagonal feels broken, and players blame the controls."""
    solid = lambda cx, cy: cy <= 1
    p = Player(100, 2 * CELL)
    moved = p.move(1, -1, solid)
    assert moved is True
    assert p.x == 101, "should have slid horizontally"
    assert p.y == 2 * CELL, "should not have moved vertically into the wall"


def test_the_room_edge_is_solid():
    p = Player(4, 4 * CELL)
    for _ in range(50):
        p.move(-1, 0, scene.is_solid)
    assert p.x >= 0


# --- cells -----------------------------------------------------------------

def test_the_player_occupies_up_to_four_cells():
    assert len(Player(40, 40).occupied_cells()) == 2      # aligned: 1 wide, 2 tall
    assert len(Player(43, 43).occupied_cells()) == 6      # straddling both axes


def test_the_feet_decide_which_row_the_player_is_in():
    """A person is two cells tall; the ground they stand on is what matters."""
    p = Player(40, 40)
    assert p.cy == (40 + HEIGHT - 1) // CELL


def test_ahead_is_the_cell_in_front():
    p = Player(80, 80, facing=S.RIGHT)
    assert p.ahead() == (p.cx + 1, p.cy)
    p.facing = S.UP
    assert p.ahead() == (p.cx, p.cy - 1)
