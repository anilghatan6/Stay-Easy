from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Optional


@dataclass(frozen=True)
class RoomCapacity:
    """
    Capacity of ONE physical room (this schema stores max_adults /
    max_children on `Rooms` itself — `RoomType` is just a name/category
    with no capacity columns of its own).
    """

    max_adults: int
    max_children: int
    max_total_occupancy: int


@dataclass(frozen=True)
class RoomAllocation:
    """One room's assigned occupants in a candidate split."""

    adults: int
    children: int


@dataclass(frozen=True)
class AllocationResult:
    feasible: bool
    rooms: list[RoomAllocation] = field(default_factory=list)
    reason: Optional[str] = None


@dataclass(frozen=True)
class SpecificRoomAllocation:
    """One chosen physical room's assigned occupants."""

    room_index: int  # index into the `rooms` list passed to the engine
    adults: int
    children: int


@dataclass(frozen=True)
class HeterogeneousAllocationResult:
    feasible: bool
    rooms: list[SpecificRoomAllocation] = field(default_factory=list)
    reason: Optional[str] = None


class HeterogeneousGuestAllocationEngine:
    """
    Same problem as GuestAllocationEngine, but `rooms` is a real list of
    per-room capacities (they don't all have to match). We need to both:
      (a) choose WHICH `room_count` rooms out of the candidates to use, and
      (b) find a valid (adults_i, children_i) split across the chosen ones.

    Approach: single left-to-right scan over the candidate rooms (sorted
    by total capacity, descending, purely as a pruning heuristic — order
    doesn't affect correctness). At each room we branch on "skip" vs.
    "use it with some valid occupant split", memoizing feasibility on
    (position, rooms_selected_so_far, remaining_adults, remaining_children).
    That state space is bounded by
    n_rooms * room_count * (total_adults+1) * (total_children+1), which
    stays small for realistic hotel inventories and DB check-constraint
    bounds (adults<=30, children<=15).
    """

    def __init__(self, rooms: list[RoomCapacity]):
        self.rooms = rooms
        # Pre-sort once; keep a mapping back to original indices so callers
        # can identify which actual Rooms.id each allocation refers to.
        self._order: list[int] = sorted(
            range(len(rooms)),
            key=lambda i: -(rooms[i].max_adults + rooms[i].max_children),
        )

    def allocate(
        self, total_adults: int, total_children: int, room_count: int
    ) -> HeterogeneousAllocationResult:
        n = len(self.rooms)
        if room_count < 1:
            return HeterogeneousAllocationResult(
                False, reason="room_count must be >= 1"
            )
        if room_count > n:
            return HeterogeneousAllocationResult(
                False,
                reason=f"Only {n} candidate room(s) available, need {room_count}.",
            )
        if total_adults < room_count:
            return HeterogeneousAllocationResult(
                False,
                reason=(
                    f"Need at least {room_count} adult(s) (one per room) but "
                    f"only {total_adults} adult(s) requested."
                ),
            )

        order, rooms = self._order, self.rooms

        @lru_cache(maxsize=None)
        def feasible(
            pos: int, selected: int, rem_adults: int, rem_children: int
        ) -> bool:
            if selected == room_count:
                return rem_adults == 0 and rem_children == 0
            if pos == n:
                return False
            if (n - pos) < (room_count - selected):
                return False  # not enough rooms left to hit the target count

            # Option 1: skip this room entirely.
            if feasible(pos + 1, selected, rem_adults, rem_children):
                return True

            # Option 2: use this room with some legal (adults_i, children_i).
            room = rooms[order[pos]]
            # Rooms still needed AFTER this one each require >= 1 adult.
            still_needed_after = room_count - selected - 1
            max_a = min(room.max_adults, rem_adults - still_needed_after)
            for adults_i in range(1, max_a + 1):
                max_c = min(
                    room.max_children, room.max_total_occupancy - adults_i, rem_children
                )
                if max_c < 0:
                    continue
                for children_i in range(0, max_c + 1):
                    if feasible(
                        pos + 1,
                        selected + 1,
                        rem_adults - adults_i,
                        rem_children - children_i,
                    ):
                        return True
            return False

        ok = feasible(0, 0, total_adults, total_children)
        if not ok:
            feasible.cache_clear()
            return HeterogeneousAllocationResult(
                False,
                reason=(
                    f"No valid split exists for {total_adults} adult(s) + "
                    f"{total_children} child(ren) across {room_count} of the "
                    f"{n} candidate room(s)."
                ),
            )

        # Reconstruct one concrete assignment, reusing `feasible` as lookahead.
        allocations: list[SpecificRoomAllocation] = []
        pos, selected = 0, 0
        rem_adults, rem_children = total_adults, total_children
        while selected < room_count:
            room = rooms[order[pos]]
            still_needed_after = room_count - selected - 1
            max_a = min(room.max_adults, rem_adults - still_needed_after)
            used = False
            for adults_i in range(1, max_a + 1):
                max_c = min(
                    room.max_children, room.max_total_occupancy - adults_i, rem_children
                )
                if max_c < 0:
                    continue
                for children_i in range(max_c, -1, -1):
                    if feasible(
                        pos + 1,
                        selected + 1,
                        rem_adults - adults_i,
                        rem_children - children_i,
                    ):
                        allocations.append(
                            SpecificRoomAllocation(order[pos], adults_i, children_i)
                        )
                        rem_adults -= adults_i
                        rem_children -= children_i
                        selected += 1
                        used = True
                        break
                if used:
                    break
            pos += 1  # whether used or skipped, move to next candidate room

        feasible.cache_clear()
        return HeterogeneousAllocationResult(True, rooms=allocations)


# ---------------------------------------------------------------------------
# 2. DYNAMIC PRICING ENGINE
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NightlyRateBreakdown:
    night: date
    base_rate: Decimal
    applied_rate: Decimal
    markup_reason: Optional[str]


@dataclass(frozen=True)
class PriceQuote:
    nights: list[NightlyRateBreakdown]
    room_count: int
    sum_per_room: Decimal
    grand_total: Decimal

    def as_formula_string(self) -> str:
        nightly_sum = " + ".join(f"{n.applied_rate}" for n in self.nights)
        return (
            f"({nightly_sum}) x {self.room_count} room(s) "
            f"= {self.sum_per_room} x {self.room_count} = {self.grand_total}"
        )





class DynamicPricingEngine:
    """
    Computes a total quote by summing a *per-night* rate across every
    individual night of the stay, then multiplying by room_count.

    seasonal_matrix: Optional[dict[date, Decimal]]
        A per-date override table (e.g. loaded from a `daily_rates` table
        keyed by (property_id/room_type_id, date)). If a date has an entry
        here, it takes priority over `base_rate`. Weekend markup is still
        applied on top of whichever base is chosen, unless you want
        seasonal rates to be markup-exempt (see `weekend_markup_applies_to_seasonal`).
    """

    def __init__(
        self,
        base_rate: Decimal,
        seasonal_matrix: Optional[dict[date, Decimal]] = None,
    ):
        self.base_rate = base_rate
        self.seasonal_matrix = seasonal_matrix or {}

    def _rate_for_night(self, night: date) -> tuple[Decimal, Optional[str]]:
        seasonal_override = self.seasonal_matrix.get(night)
        rate = seasonal_override if seasonal_override is not None else self.base_rate
        reason_parts = []
        if seasonal_override is not None:
            reason_parts.append("seasonal override")

        return rate, (", ".join(reason_parts) if reason_parts else None)

    def quote(self, check_in: date, check_out: date, room_count: int) -> PriceQuote:
        if check_out <= check_in:
            raise ValueError("check_out must be after check_in")
        if room_count < 1:
            raise ValueError("room_count must be >= 1")

        nights: list[NightlyRateBreakdown] = []
        current = check_in
        while current < check_out:
            applied_rate, reason = self._rate_for_night(current)
            nights.append(
                NightlyRateBreakdown(
                    night=current,
                    base_rate=self.seasonal_matrix.get(current, self.base_rate),
                    applied_rate=applied_rate,
                    markup_reason=reason,
                )
            )
            current += timedelta(days=1)

        sum_per_room = sum((n.applied_rate for n in nights), Decimal("0"))
        grand_total = (sum_per_room * room_count).quantize(Decimal("0.01"))

        return PriceQuote(
            nights=nights,
            room_count=room_count,
            sum_per_room=sum_per_room,
            grand_total=grand_total,
        )


def calculate_stay_total(
    room_base_rates: list[Decimal],
    check_in: date,
    check_out: date,
    seasonal_matrix: Optional[dict[date, Decimal]] = None,
) -> Decimal:
    """
    Prices a SPECIFIC set of rooms (as returned by
    HeterogeneousGuestAllocationEngine — the rooms actually needed for a
    search's room_count) over the full stay. Rooms with the same
    base_rate are batched through one DynamicPricingEngine.quote() call;
    rooms with different rates (common, since capacity/price live on
    individual Rooms) are priced separately and summed.

    This is what powers the "price" shown in search results: total cost
    for THIS stay, THESE dates, THESE specific rooms — not a generic
    per-night number.
    """
    from collections import Counter

    total = Decimal("0")
    for rate, count in Counter(room_base_rates).items():
        quote = DynamicPricingEngine(
            base_rate=rate, seasonal_matrix=seasonal_matrix
        ).quote(check_in=check_in, check_out=check_out, room_count=count)
        total += quote.grand_total
    return total.quantize(Decimal("0.01"))
