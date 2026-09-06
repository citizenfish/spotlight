"""Player movement, facing and collision."""

from spikes import scene, sources as S
from spikes.layout import PLAY_ROWS
from spikes.player import HEIGHT, NUDGE, SPEED, WIDTH, Player
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


# --- corner assist ---------------------------------------------------------

def _one_cell_doorway():
    """A solid wall across row 9 with a single-cell gap at column 5."""
    def is_solid(cx, cy):
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return True
        return cy == 9 and cx != 5
    return is_solid


def test_a_one_cell_doorway_is_passable_from_any_alignment():
    """Without assist only one x in eight fits, which reads as broken controls."""
    solid = _one_cell_doorway()
    for x in range(5 * CELL - NUDGE, 5 * CELL + NUDGE + 1):
        p = Player(x, 7 * CELL)
        for _ in range(60):
            p.move(0, 1, solid)
        assert p.y > 9 * CELL, f"stuck at x={x} (offset {x % CELL})"


def test_assist_works_horizontally_too():
    def solid(cx, cy):
        if not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS):
            return True
        return cx == 9 and cy not in (5, 6)
    for y in range(5 * CELL - NUDGE, 5 * CELL + NUDGE + 1):
        p = Player(4 * CELL, y)
        for _ in range(80):
            p.move(1, 0, solid)
        assert p.x > 9 * CELL, f"stuck at y={y}"


def test_assist_never_puts_the_player_inside_a_wall():
    solid = _one_cell_doorway()
    p = Player(5 * CELL + 3, 7 * CELL)
    for _ in range(200):
        p.move(0, 1, solid)
        p.move(1, 0, solid)
        for cx, cy in p.occupied_cells():
            assert not solid(cx, cy), f"ended up inside a wall at {cx},{cy}"


def test_assist_cannot_tunnel_through_a_solid_wall():
    """A wall with no gap must stay a wall, however hard you push."""
    solid = lambda cx, cy: cy == 9 or not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS)
    p = Player(5 * CELL, 7 * CELL)
    for _ in range(200):
        p.move(0, 1, solid)
    assert p.y + HEIGHT - 1 < 9 * CELL, "tunnelled through a solid wall"


def test_the_nudge_is_bounded():
    solid = _one_cell_doorway()
    p = Player(5 * CELL + NUDGE + 2, 7 * CELL)   # too far out to be helped
    start = p.x
    p.move(0, 1, solid)
    assert abs(p.x - start) <= NUDGE


def test_walking_in_the_open_is_never_nudged():
    """Assist must not make straight-line movement drift."""
    open_world = lambda cx, cy: not (0 <= cx < COLS and 0 <= cy < PLAY_ROWS)
    p = Player(100, 100)
    for _ in range(50):
        p.move(1, 0, open_world)
    assert p.y == 100, "drifted while walking in a straight line"
