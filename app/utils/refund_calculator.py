from datetime import datetime, timezone

from app.modules.pms.models.rooms_model import CancellationPolicy


def calculate_single_room_refund(
    cancellation_policy: CancellationPolicy,
    hours_until_checkin: float,
    room_amount_paid: float,
) -> float:
    """Calculate refund for a single room based on its own cancellation policy."""
    if cancellation_policy == CancellationPolicy.FLEXIBLE:
        if hours_until_checkin > 24:
            return room_amount_paid
        return 0.0

    elif cancellation_policy == CancellationPolicy.MODERATE:
        if hours_until_checkin > 120:
            return room_amount_paid
        return 0.0

    elif cancellation_policy == CancellationPolicy.STRICT:
        if hours_until_checkin > 168:
            return room_amount_paid * 0.5
        return 0.0

    elif cancellation_policy == CancellationPolicy.NON_REFUNDABLE:
        return 0.0

    elif cancellation_policy == CancellationPolicy.CUSTOM:
        return 0.0

    return 0.0


def calculate_refund_amount(
    booking, room_units: list
) -> tuple[float, list[dict]]:
    """Calculate refund amount based on each room's cancellation policy and timing.

    Returns:
        A tuple of (total_refund_amount, per_room_details) where per_room_details
        is a list of dicts containing per-room refund breakdown info.
    """
    from app.modules.booking.models.booking_model import MasterBookingStatus

    amount_paid = float(booking.amount_paid)

    # PENDING bookings: always full refund (typically 0 if unpaid)
    if booking.status == MasterBookingStatus.PENDING:
        per_room_details = []
        for room in room_units:
            per_room_details.append({
                "room_name": room.room_name,
                "room_type": room.room_type.room_type_name if room.room_type else "",
                "cancellation_title": room.cancellation_title,
                "cancellation_description": room.cancellation_description,
                "cancellation_policy": room.cancellation_policy,
                "room_refund_amount": 0.0,
            })
        return amount_paid, per_room_details

    # For CONFIRMED bookings, calculate per-room refund based on each room's policy
    now = datetime.now(timezone.utc)
    checkin = datetime.combine(
        booking.checkin_date, datetime.min.time(), tzinfo=timezone.utc
    )
    hours_until_checkin = (checkin - now).total_seconds() / 3600

    nights = (booking.checkout_date - booking.checkin_date).days

    # Calculate proportional allocation: each room's share of amount_paid
    total_subtotal = sum(float(r.base_rate) * nights for r in room_units)
    if total_subtotal == 0:
        # Fallback: equal distribution if subtotal is zero
        per_room_share = amount_paid / len(room_units) if room_units else 0
    else:
        per_room_share = None  # Will compute per room below

    total_refund = 0.0
    per_room_details = []

    for room in room_units:
        room_subtotal = float(room.base_rate) * nights
        if per_room_share is not None:
            room_amount_paid = per_room_share
        else:
            room_amount_paid = (
                (room_subtotal / total_subtotal) * amount_paid
                if total_subtotal > 0
                else amount_paid / len(room_units)
            )

        room_refund = calculate_single_room_refund(
            room.cancellation_policy, hours_until_checkin, room_amount_paid
        )

        total_refund += room_refund
        per_room_details.append({
            "room_name": room.room_name,
            "room_type": room.room_type.room_type_name if room.room_type else "",
            "cancellation_title": room.cancellation_title,
            "cancellation_description": room.cancellation_description,
            "cancellation_policy": room.cancellation_policy,
            "room_refund_amount": room_refund,
        })

    return total_refund, per_room_details
