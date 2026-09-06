"""Flyspray: lingering patches, charges, and what they kill."""

from types import SimpleNamespace

from spikes import sources as S
from spikes.layout import PLAY_ROWS
from spikes.spray import PATCH_FRAMES, Spray, patch_cells
from spotlight.core.constants import COLS


def _cleg(cx, cy):
    return SimpleNamespace(cx=cx, cy=cy)


# --- laying a patch --------------------------------------------------------

def test_the_patch_lands_ahead_in_the_facing_direction():
    for facing, (fx, fy) in ((S.RIGHT, (1, 0)), (S.LEFT, (-1, 0)),
                             (S.UP, (0, -1)), (S.DOWN, (0, 1))):
        cells = set(patch_cells(10, 10, facing))
        assert (10 + fx, 10 + fy) in cells, f"nothing ahead facing {facing}"
        assert (10 - fx, 10 - fy) not in cells, f"sprayed behind, facing {facing}"


def test_you_do_not_spray_your_own_cell():
    for facing in (S.UP, S.DOWN, S.LEFT, S.RIGHT):
        assert (10, 10) not in set(patch_cells(10, 10, facing))


def test_the_patch_is_clipped_at_the_room_edge():
    for cells in (patch_cells(0, 0, S.LEFT), patch_cells(COLS - 1, PLAY_ROWS - 1,
                                                         S.DOWN)):
        for cx, cy in cells:
            assert 0 <= cx < COLS and 0 <= cy < PLAY_ROWS


def test_firing_lays_ground_that_covers():
    sp = Spray(charges=3)
    assert sp.fire(10, 10, S.RIGHT) is True
    assert sp.covers(11, 10)
    assert not sp.covers(9, 10)


# --- charges ---------------------------------------------------------------

def test_charges_run_out():
    sp = Spray(charges=2)
    assert sp.fire(5, 5, S.UP) is True
    assert sp.fire(5, 5, S.UP) is True
    assert sp.empty
    assert sp.fire(5, 5, S.UP) is False


def test_a_failed_shot_lays_nothing():
    sp = Spray(charges=0)
    sp.fire(5, 5, S.UP)
    assert not sp.patches


# --- lingering -------------------------------------------------------------

def test_a_patch_expires():
    sp = Spray()
    sp.fire(10, 10, S.RIGHT)
    for _ in range(PATCH_FRAMES - 1):
        sp.tick()
    assert sp.covers(11, 10), "cleared too early"
    sp.tick()
    assert not sp.covers(11, 10)


def test_respraying_refreshes_rather_than_stacking():
    """There is no such thing as doubly-poisoned ground."""
    sp = Spray(charges=5)
    sp.fire(10, 10, S.RIGHT)
    for _ in range(PATCH_FRAMES // 2):
        sp.tick()
    sp.fire(10, 10, S.RIGHT)
    for _ in range(PATCH_FRAMES - 1):
        sp.tick()
    assert sp.covers(11, 10), "refresh did not reset the clock"


def test_patches_expire_independently():
    sp = Spray(charges=5)
    sp.fire(10, 10, S.RIGHT)
    for _ in range(PATCH_FRAMES // 2):
        sp.tick()
    sp.fire(20, 10, S.RIGHT)
    for _ in range(PATCH_FRAMES // 2 + 1):
        sp.tick()
    assert not sp.covers(11, 10), "the older patch should have gone"
    assert sp.covers(21, 10), "the newer patch should remain"


# --- killing ---------------------------------------------------------------

def test_clegs_standing_in_spray_die():
    sp = Spray()
    sp.fire(10, 10, S.RIGHT)
    inside, outside = _cleg(11, 10), _cleg(2, 2)
    assert sp.kills([inside, outside]) == [inside]


def test_nothing_dies_once_the_patch_has_cleared():
    sp = Spray()
    sp.fire(10, 10, S.RIGHT)
    for _ in range(PATCH_FRAMES):
        sp.tick()
    assert sp.kills([_cleg(11, 10)]) == []


def test_an_empty_sprayer_kills_nothing():
    sp = Spray(charges=0)
    sp.fire(10, 10, S.RIGHT)
    assert sp.kills([_cleg(11, 10)]) == []
