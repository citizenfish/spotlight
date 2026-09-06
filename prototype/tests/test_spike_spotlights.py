"""Carried spotlights, dropped ones, and swapping between them."""

from spikes import lighting as L, scene
from spikes.player import Player
from spikes.sources import Cone
from spikes.spotlights import FloorLight, Spotlights


def _kit(carried_power=100, carried_lit=True, floor_power=500,
         floor_lit=False):
    px, py = scene.PLAYER_START
    player = Player(px, py)
    cone = Cone(reach=7, power=carried_power)
    cone.enabled = carried_lit
    light = FloorLight(player.cx, player.cy, power=floor_power, lit=floor_lit)
    return Spotlights(cone, [light]), player, light


def _step_off_and_back(kit, player):
    """Far enough to actually change the feet cell, and back."""
    start = (player.cx, player.cy)
    for _ in range(16):
        player.move(0, 1, lambda cx, cy: False)
        kit.tick(player)
    assert (player.cx, player.cy) != start, "did not leave the cell"
    while (player.cx, player.cy) != start:
        player.move(0, -1, lambda cx, cy: False)
        kit.tick(player)


# --- the carried light -----------------------------------------------------

def test_the_toggle_switches_the_carried_light():
    kit, _, _ = _kit(carried_lit=False)
    assert kit.toggle() is True
    assert kit.cone.enabled is True
    assert kit.toggle() is False


def test_power_falls_only_while_lit():
    kit, player, _ = _kit(carried_lit=False, floor_power=0)
    before = kit.cone.power
    for _ in range(20):
        kit.tick(player)
    assert kit.cone.power == before, "an unlit spotlight must not drain"
    kit.toggle()
    for _ in range(20):
        kit.tick(player)
    assert kit.cone.power == before - 20


def test_a_spent_carried_light_gives_no_cone():
    kit, _, _ = _kit(carried_power=1)
    field = L.LightField()
    for _ in range(5):
        kit.cone.drain()
    field.begin(); kit.cone.apply(field); field.commit()
    assert not any(field.charge), "a dead spotlight still lit something"


# --- drop by swap ----------------------------------------------------------

def test_walking_onto_a_spotlight_swaps_it_for_the_carried_one():
    kit, player, light = _kit(carried_power=100, carried_lit=True,
                              floor_power=500, floor_lit=False)
    assert kit.tick(player) is light
    assert kit.cone.power == 500 and kit.cone.enabled is False
    assert light.power > 0 and light.lit is True


def test_the_old_light_is_left_under_the_players_feet():
    kit, player, light = _kit()
    kit.tick(player)
    assert (light.cx, light.cy) == (player.cx, player.cy)


def test_a_light_beside_your_head_is_not_collected():
    """A person straddles up to six cells; only the feet cell counts."""
    kit, player, light = _kit()
    overlapped = player.occupied_cells() - {(player.cx, player.cy)}
    light.cx, light.cy = sorted(overlapped)[0]
    assert kit.tick(player) is None
    assert kit.swaps == 0


def test_a_light_dropped_burning_goes_on_burning():
    """That is what makes it bait."""
    kit, player, light = _kit(carried_lit=True)
    kit.tick(player)
    assert light.burning
    field = L.LightField()
    field.begin(); kit.apply(field); field.commit()
    assert field.level_at(light.cx, light.cy) == L.LIT


def test_a_light_dropped_switched_off_just_lies_there():
    kit, player, light = _kit(carried_lit=False)
    kit.tick(player)
    assert not light.burning
    field = L.LightField()
    field.begin(); kit.apply(field); field.commit()
    assert not any(field.charge)


def test_you_do_not_instantly_pick_back_up_what_you_just_dropped():
    """Otherwise standing on a spotlight swaps every single frame."""
    kit, player, _ = _kit()
    kit.tick(player)
    for _ in range(60):
        kit.tick(player)
    assert kit.swaps == 1


def test_stepping_off_and_back_on_lets_you_pick_it_up_again():
    kit, player, _ = _kit()
    kit.tick(player)
    assert kit.swaps == 1
    _step_off_and_back(kit, player)
    assert kit.swaps == 2


# --- burning down ----------------------------------------------------------

def test_a_burning_floor_light_runs_out_and_goes_dark():
    light = FloorLight(5, 5, power=10, lit=True)
    for _ in range(10):
        light.tick()
    assert light.spent and not light.burning and not light.lit


def test_an_unlit_floor_light_does_not_burn_down():
    light = FloorLight(5, 5, power=10, lit=False)
    for _ in range(50):
        light.tick()
    assert light.power == 10


def test_a_spent_light_cannot_be_picked_up():
    kit, player, light = _kit(floor_power=0)
    assert kit.tick(player) is None
    assert kit.swaps == 0


def test_a_floor_light_lights_a_disc_around_itself():
    """It is lying on the ground; nobody is aiming it."""
    light = FloorLight(10, 10, power=100, lit=True)
    field = L.LightField()
    field.begin(); light.emit(field); field.commit()
    assert field.level_at(10, 10) == L.LIT
    assert field.level_at(12, 10) == L.LIT
    assert field.level_at(12, 12) == L.DARK, "corner should be outside the disc"
