import uuid
import pytest
from httpx import AsyncClient

from tests.modules.booking.conftest import future_date


def _admin_headers(store: dict) -> dict:
    return {"Authorization": f"Bearer {store['bk_access_token']}"}


# ============================================================
# Section A: Unauthenticated — all endpoints → 401/403
# ============================================================

@pytest.mark.asyncio
async def test_create_booking_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post("/bookings/", json={"idempotency_key": "x"})
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_payment_intent_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post(
        "/bookings/BK-FAKE/payment-intent",
        json={"payment_method": "ONLINE", "payment_gateway": "DUMMY"},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_confirm_payment_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post(
        "/bookings/BK-FAKE/confirm",
        json={"idempotency_key": "x", "gateway_payload": {}},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_apply_discount_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post(
        "/bookings/BK-FAKE/apply-discount", json={"code": "SAVE10"}
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_my_bookings_unauthenticated(async_client: AsyncClient):
    resp = await async_client.get("/bookings/me")
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_booking_unauthenticated(async_client: AsyncClient):
    resp = await async_client.get("/bookings/BK-FAKE")
    assert resp.status_code in (401, 403), resp.text


# ============================================================
# Section B: Validation — POST /bookings/ with bad payloads
# ============================================================

@pytest.mark.asyncio
async def test_create_booking_checkin_equals_checkout(
    booking_guest_client: AsyncClient,
):
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "property_id": "00000000-0000-0000-0000-000000000000",
        "room_ids": ["00000000-0000-0000-0000-000000000000"],
        "check_in": future_date(10),
        "check_out": future_date(10),
        "adults": 2,
    }
    resp = await booking_guest_client.post("/bookings/", json=payload)
    assert resp.status_code == 400, resp.text
    assert "strictly before" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_create_booking_checkin_in_past(
    booking_guest_client: AsyncClient,
):
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "property_id": "00000000-0000-0000-0000-000000000000",
        "room_ids": ["00000000-0000-0000-0000-000000000000"],
        "check_in": future_date(-5),
        "check_out": future_date(10),
        "adults": 2,
    }
    resp = await booking_guest_client.post("/bookings/", json=payload)
    assert resp.status_code == 400, resp.text
    assert "past" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_create_booking_invalid_property(
    booking_guest_client: AsyncClient,
):
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "property_id": "00000000-0000-0000-0000-000000000099",
        "room_ids": ["00000000-0000-0000-0000-000000000099"],
        "check_in": future_date(10),
        "check_out": future_date(13),
        "adults": 2,
    }
    resp = await booking_guest_client.post("/bookings/", json=payload)
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_create_booking_validation_errors(
    booking_guest_client: AsyncClient,
):
    payload = {
        "idempotency_key": "",
        "property_id": "not-a-uuid",
        "room_ids": [],
        "check_in": "invalid-date",
        "check_out": "invalid-date",
        "adults": 0,
        "children": -1,
    }
    resp = await booking_guest_client.post("/bookings/", json=payload)
    assert resp.status_code == 422, resp.text


# ============================================================
# Section C: Full booking lifecycle — happy path
# ============================================================

@pytest.mark.asyncio
async def test_create_booking_success(
    booking_guest_client: AsyncClient, bk_room_setup: dict
):
    data = bk_room_setup
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "property_id": data["bk_property_id"],
        "room_ids": [data["bk_room_id"]],
        "check_in": future_date(30),
        "check_out": future_date(33),
        "adults": 2,
        "children": 1,
    }
    resp = await booking_guest_client.post("/bookings/", json=payload)
    assert resp.status_code == 201, resp.text
    result = resp.json()["data"]
    assert result["status"] == "PENDING"
    assert result["ref_number"].startswith("BK-")
    assert result["soft_lock_expires_at"] is not None
    assert result["check_in"] == future_date(30)
    assert result["check_out"] == future_date(33)
    assert result["nights"] == 3
    assert result["total_amount"] == 600.0
    assert result["subtotal"] == 600.0
    assert result["special_offer_discount"] == 0.0
    assert len(result["rooms"]) == 1
    assert result["rooms"][0]["room_id"] == data["bk_room_id"]
    assert result["property"]["id"] == data["bk_property_id"]
    data["bk_ref_number"] = result["ref_number"]
    data["bk_booking_id"] = result["booking_id"]


@pytest.mark.asyncio
async def test_payment_intent_success(
    booking_guest_client: AsyncClient, bk_room_setup: dict
):
    ref_number = bk_room_setup["bk_ref_number"]
    resp = await booking_guest_client.post(
        f"/bookings/{ref_number}/payment-intent",
        json={"payment_method": "ONLINE", "payment_gateway": "DUMMY"},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["data"]
    assert result["ref_number"] == ref_number
    assert result["payment_gateway"] == "DUMMY"
    assert result["payment_method"] == "ONLINE"
    assert result["amount"] == 600.0
    assert result["currency"] == "USD"
    assert result["payment_intent_id"] is not None
    assert result["client_secret"] is not None


@pytest.mark.asyncio
async def test_confirm_payment_success(
    booking_guest_client: AsyncClient, bk_room_setup: dict
):
    ref_number = bk_room_setup["bk_ref_number"]
    resp = await booking_guest_client.post(
        f"/bookings/{ref_number}/confirm",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "gateway_payload": {},
        },
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["data"]
    assert result["status"] == "CONFIRMED"
    assert result["booking_id"] == bk_room_setup["bk_booking_id"]
    assert result["ref_number"] == ref_number


@pytest.mark.asyncio
async def test_get_booking_detail_success(
    booking_guest_client: AsyncClient, bk_room_setup: dict
):
    ref_number = bk_room_setup["bk_ref_number"]
    resp = await booking_guest_client.get(f"/bookings/{ref_number}")
    assert resp.status_code == 200, resp.text
    result = resp.json()["data"]
    assert result["ref_number"] == ref_number
    assert result["status"] == "CONFIRMED"
    assert result["booking_id"] == bk_room_setup["bk_booking_id"]
    assert result["check_in"] == future_date(30)
    assert result["check_out"] == future_date(33)
    assert len(result["rooms"]) == 1
    assert result["property"] is not None


# ============================================================
# Section D: Idempotency — POST /bookings/
# ============================================================

@pytest.mark.asyncio
async def test_create_booking_idempotent(
    booking_guest_client: AsyncClient, bk_room_setup: dict
):
    idem_key = str(uuid.uuid4())
    payload = {
        "idempotency_key": idem_key,
        "property_id": bk_room_setup["bk_property_id"],
        "room_ids": [bk_room_setup["bk_room_id_2"]],
        "check_in": future_date(40),
        "check_out": future_date(43),
        "adults": 1,
    }
    resp1 = await booking_guest_client.post("/bookings/", json=payload)
    assert resp1.status_code == 201, resp1.text

    resp2 = await booking_guest_client.post("/bookings/", json=payload)
    assert resp2.status_code == 201, resp2.text
    assert resp1.json()["data"]["ref_number"] == resp2.json()["data"]["ref_number"]
    assert resp1.json()["data"]["booking_id"] == resp2.json()["data"]["booking_id"]

    bk_room_setup["bk_ref_number_2"] = resp1.json()["data"]["ref_number"]


@pytest.mark.asyncio
async def test_create_booking_rooms_already_booked(
    booking_guest_client: AsyncClient, bk_room_setup: dict
):
    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "property_id": bk_room_setup["bk_property_id"],
        "room_ids": [bk_room_setup["bk_room_id"]],
        "check_in": future_date(30),
        "check_out": future_date(33),
        "adults": 1,
    }
    resp = await booking_guest_client.post("/bookings/", json=payload)
    assert resp.status_code == 400, resp.text


# ============================================================
# Section E: Payment intent edge cases
# ============================================================

@pytest.mark.asyncio
async def test_payment_intent_invalid_gateway(
    booking_guest_client: AsyncClient, bk_room_setup: dict
):
    ref_number = bk_room_setup["bk_ref_number"]
    resp = await booking_guest_client.post(
        f"/bookings/{ref_number}/payment-intent",
        json={"payment_method": "ONLINE", "payment_gateway": "BITCOIN"},
    )
    assert resp.status_code == 400, resp.text
    assert "Unsupported" in resp.json()["error"]


@pytest.mark.asyncio
async def test_payment_intent_not_found(booking_guest_client: AsyncClient):
    resp = await booking_guest_client.post(
        "/bookings/BK-NONEXISTENT/payment-intent",
        json={"payment_method": "ONLINE", "payment_gateway": "DUMMY"},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_payment_intent_already_confirmed(
    booking_guest_client: AsyncClient, bk_room_setup: dict
):
    ref_number = bk_room_setup["bk_ref_number"]
    resp = await booking_guest_client.post(
        f"/bookings/{ref_number}/payment-intent",
        json={"payment_method": "ONLINE", "payment_gateway": "DUMMY"},
    )
    assert resp.status_code == 400, resp.text
    assert "already been paid for" in resp.json()["error"].lower()


# ============================================================
# Section F: Confirm payment edge cases
# ============================================================

@pytest.mark.asyncio
async def test_confirm_payment_not_found(booking_guest_client: AsyncClient):
    resp = await booking_guest_client.post(
        "/bookings/BK-NONEXISTENT/confirm",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "gateway_payload": {},
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_confirm_payment_already_confirmed(
    booking_guest_client: AsyncClient, bk_room_setup: dict
):
    ref_number = bk_room_setup["bk_ref_number"]
    resp = await booking_guest_client.post(
        f"/bookings/{ref_number}/confirm",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "gateway_payload": {},
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "CONFIRMED"
    assert "already confirmed" in resp.json()["data"]["message"].lower()


@pytest.mark.asyncio
async def test_confirm_payment_verify_fail(
    booking_guest_client: AsyncClient, bk_room_setup: dict, mocker
):
    from app.modules.booking.services.payment_service import PaymentService

    idem_key = str(uuid.uuid4())
    payload = {
        "idempotency_key": idem_key,
        "property_id": bk_room_setup["bk_property_id"],
        "room_ids": [bk_room_setup["bk_room_id_2"]],
        "check_in": future_date(50),
        "check_out": future_date(53),
        "adults": 1,
    }
    resp = await booking_guest_client.post("/bookings/", json=payload)
    assert resp.status_code == 201, resp.text
    ref_number = resp.json()["data"]["ref_number"]
    bk_room_setup["bk_ref_number_3"] = ref_number

    mocker.patch.object(PaymentService, "verify", return_value=False)

    resp = await booking_guest_client.post(
        f"/bookings/{ref_number}/confirm",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "gateway_payload": {},
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "PAYMENT_NOT_VERIFIED"


# ============================================================
# Section G: Discount code
# ============================================================

@pytest.mark.asyncio
async def test_apply_discount_success(
    booking_guest_client: AsyncClient, bk_room_setup: dict, bk_discount_setup: dict
):
    idem_key = str(uuid.uuid4())
    payload = {
        "idempotency_key": idem_key,
        "property_id": bk_room_setup["bk_property_id"],
        "room_ids": [bk_room_setup["bk_room_id"]],
        "check_in": future_date(60),
        "check_out": future_date(63),
        "adults": 1,
    }
    resp = await booking_guest_client.post("/bookings/", json=payload)
    assert resp.status_code == 201, resp.text
    ref_number = resp.json()["data"]["ref_number"]

    resp = await booking_guest_client.post(
        f"/bookings/{ref_number}/apply-discount",
        json={"code": bk_discount_setup["bk_discount_code"]},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["data"]
    assert result["coupon_code"] == "BOOKING10"
    assert result["coupon_discount"] > 0
    expected_total = 600.0 - 60.0
    assert result["total_amount"] == expected_total


@pytest.mark.asyncio
async def test_apply_discount_invalid_code(
    booking_guest_client: AsyncClient, bk_room_setup: dict
):
    ref_number = bk_room_setup.get("bk_ref_number_3")
    if not ref_number:
        idem_key = str(uuid.uuid4())
        payload = {
            "idempotency_key": idem_key,
            "property_id": bk_room_setup["bk_property_id"],
            "room_ids": [bk_room_setup["bk_room_id"]],
            "check_in": future_date(70),
            "check_out": future_date(73),
            "adults": 1,
        }
        resp = await booking_guest_client.post("/bookings/", json=payload)
        assert resp.status_code == 201, resp.text
        ref_number = resp.json()["data"]["ref_number"]

    resp = await booking_guest_client.post(
        f"/bookings/{ref_number}/apply-discount",
        json={"code": "INVALID99"},
    )
    assert resp.status_code == 400, resp.text


# ============================================================
# Section H: My bookings
# ============================================================

@pytest.mark.asyncio
async def test_get_my_bookings_as_guest(
    booking_guest_client: AsyncClient,
):
    resp = await booking_guest_client.get("/bookings/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    data = body["data"]
    meta = body["meta"]
    assert len(data["items"]) >= 4
    assert meta["total"] >= 4
    assert meta["skip"] == 0
    assert meta["limit"] == 10
    assert isinstance(meta["has_more"], bool)


@pytest.mark.asyncio
async def test_get_my_bookings_pagination(booking_guest_client: AsyncClient):
    resp = await booking_guest_client.get("/bookings/me?skip=0&limit=2")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    data = body["data"]
    meta = body["meta"]
    assert len(data["items"]) <= 2
    assert meta["limit"] == 2
    assert meta["skip"] == 0
    assert meta["total"] >= 4


@pytest.mark.asyncio
async def test_get_my_bookings_other_guest(
    booking_second_guest_client: AsyncClient,
):
    resp = await booking_second_guest_client.get("/bookings/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    data = body["data"]
    meta = body["meta"]
    assert data["items"] == []
    assert meta["total"] == 0
    assert meta["has_more"] is False


# ============================================================
# Section I: Get booking detail edge cases
# ============================================================

@pytest.mark.asyncio
async def test_get_booking_detail_not_found(booking_guest_client: AsyncClient):
    resp = await booking_guest_client.get("/bookings/BK-NONEXISTENT")
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_get_booking_detail_not_owner(
    booking_second_guest_client: AsyncClient, bk_room_setup: dict
):
    ref_number = bk_room_setup["bk_ref_number"]
    resp = await booking_second_guest_client.get(f"/bookings/{ref_number}")
    assert resp.status_code == 400, resp.text
