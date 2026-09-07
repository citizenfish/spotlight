"""Carried and dropped spotlights.

The carried light is a cone you switch on and off with its own button, draining
only while lit. Spotlights also lie about the building as pickups, with varying
power.

**Drop-by-swap.** Walking onto a fresh spotlight leaves the one you were
carrying where you stood, in whatever state it was in. Both buttons are already
spoken for -- fire is the flyspray, the second is the toggle -- so there is no
key left for dropping, and this needs none. It also makes putting a light down a
*routing* decision rather than a keypress: to leave a lure behind, you have to
walk over another one.

A light dropped while burning goes on burning, and pulls Clegs to it. A light
dropped switched off just lies there as a spare.
"""

from .lighting import CHARGE_LIT, LIT

#: A dropped spotlight lights all round it, not in a cone -- nobody is aiming it.
FLOOR_RADIUS = 2


class FloorLight:
    """A spotlight lying on the ground."""

    __slots__ = ("cx", "cy", "power", "lit", "radius", "room", "_held_off")

    def __init__(self, cx: int, cy: int, power: int, lit: bool = False,
                 radius: int = FLOOR_RADIUS, room: int = 0) -> None:
        self.cx, self.cy = cx, cy
        #: Which room it is lying in. A light burning on the floor lights that
        #: room and lures the flies in it, and light does not cross a threshold
        #: (issue #21) -- so a light left behind in the room you have just left
        #: is exactly the bait the design wants and exactly the bait you can no
        #: longer see.
        self.room = room
        self.power = power
        self.lit = lit
        self.radius = radius
        # Set when this light was just dropped, so the player standing on it
        # does not instantly pick it straight back up.
        self._held_off = False

    @property
    def spent(self) -> bool:
        return self.power <= 0

    @property
    def burning(self) -> bool:
        return self.lit and not self.spent

    def tick(self) -> None:
        """Burn down, if alight."""
        if self.burning:
            self.power -= 1
            if self.power <= 0:
                self.lit = False

    def emit(self, field) -> None:
        if not self.burning:
            return
        r2 = self.radius * self.radius
        for dy in range(-self.radius, self.radius + 1):
            for dx in range(-self.radius, self.radius + 1):
                if dx * dx + dy * dy <= r2:
                    field.add(self.cx + dx, self.cy + dy, LIT, CHARGE_LIT)


class Spotlights:
    """The carried cone, plus every spotlight on the floor."""

    def __init__(self, cone, floor_lights: list[FloorLight] | None = None):
        self.cone = cone
        self.floor = list(floor_lights or [])
        self.swaps = 0

    # --- the carried light -------------------------------------------------

    def toggle(self) -> bool:
        """The second action button."""
        return self.cone.toggle()

    def tick(self, player, room: int = 0) -> FloorLight | None:
        """One frame: burn down, and swap if the player is standing on one.

        Returns the light just picked up, or None. `room` is the room the player
        is in: every spotlight in the building burns down wherever it lies, but
        you can only pick up one you are standing on, and a cell reference in
        another room is a different place with the same number.
        """
        self.cone.drain()
        for light in self.floor:
            light.tick()
        return self._maybe_swap(player, room)

    # --- swapping ----------------------------------------------------------

    def _maybe_swap(self, player, room: int = 0) -> FloorLight | None:
        """Pickup is the cell under the player's feet, not any cell their
        sprite overlaps.

        A person is 8x16 and straddles up to six cells, so testing the whole box
        would let you collect a spotlight beside your head. The feet cell is
        also exactly where a dropped light lands, which keeps picking up and
        putting down symmetrical and predictable.
        """
        standing_on = (player.cx, player.cy)
        for light in self.floor:
            on_it = light.room == room and (light.cx, light.cy) == standing_on
            if not on_it:
                # Stepping off clears the hold, so it can be collected again.
                light._held_off = False
                continue
            if light._held_off or light.spent:
                continue
            self._swap_with(light, player, room)
            return light
        return None

    def _swap_with(self, light: FloorLight, player, room: int = 0) -> None:
        """Take the floor light; leave the carried one where the player stands."""
        carried_power, carried_lit = self.cone.power, self.cone.enabled

        self.cone.power = light.power
        self.cone.enabled = light.lit

        light.power, light.lit = carried_power, carried_lit
        light.cx, light.cy = player.cx, player.cy
        light.room = room
        # The player is standing on what they just put down.
        light._held_off = True
        self.swaps += 1

    # --- what Clegs steer for ----------------------------------------------

    def floor_lures(self, room: int = 0) -> list[tuple[int, int, int, int]]:
        """Every spotlight burning on the ground, and how far it carries.

        A light on the floor pulls exactly as hard as one in your hand, which
        is the whole of baiting: leave one burning, walk away in the dark, and
        the swarm goes to it instead of to you.

        Billed to its own bucket rather than to the carried torch (issue #22).
        Bait you left behind on purpose and a light burning in your hand are
        the same lure to a Cleg and completely different decisions to a player,
        so a report that could not tell them apart would be measuring the wrong
        thing.
        """
        from .sources import FAR, LURE_FLOOR
        return [(l.cx, l.cy, FAR, LURE_FLOOR) for l in self.floor
                if l.burning and l.room == room]

    # --- lighting ----------------------------------------------------------

    def apply(self, field, room: int = 0) -> None:
        """Light one room's field. A light belongs to the room it lies in."""
        for light in self.floor:
            if light.room == room:
                light.emit(field)
