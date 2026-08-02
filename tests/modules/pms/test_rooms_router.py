"""
Tests for /properties/{property_id}/rooms/* endpoints.

Depends on `pms_client` + `pms_token_store` (from pms/conftest.py).
"""
import uuid
import pytest
from httpx import AsyncClient


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


ROOM_TYPE_PAYLOAD = {"room_type_name": "Deluxe Suite"}
BED_TYPE_PAYLOAD = {"bed_name": "King"}


def _room_payload(room_type_id: str, bed_type_id: str, **overrides) -> dict:
    base = {
        "room_name": "101",
        "floor_number": 1,
        "max_adults": 2,
        "max_children": 1,
        "base_rate": "150.00",
        "status": "AVAILABLE",
        "cancellation_policy": "FLEXIBLE",
        "room_type_id": room_type_id,
        "bed_type_id": bed_type_id,
        "photos": {"cover": None, "gallery": []},
        "system_amenity_ids": [],
        "custom_amenities": [],
    }
    base.update(overrides)
    return {"rooms": [base]}


# ────────────────────────────────────────────────────────────────────────────
# Unauthenticated — all endpoints without token → 401/403
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_rooms_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/rooms",
        json={"rooms": [{"room_name": "X"}]},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_rooms_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.get(
        "/properties/00000000-0000-0000-0000-000000000000/rooms",
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_room_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.get(
        "/properties/00000000-0000-0000-0000-000000000000/rooms/00000000-0000-0000-0000-000000000000",
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_update_room_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.patch(
        "/properties/00000000-0000-0000-0000-000000000000/rooms/00000000-0000-0000-0000-000000000000",
        json={"room_name": "Hacked"},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_delete_room_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.delete(
        "/properties/00000000-0000-0000-0000-000000000000/rooms/00000000-0000-0000-0000-000000000000",
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_create_room_type_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/rooms/room-type",
        json={"room_type_name": "Standard"},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_create_bed_type_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/rooms/bed-type",
        json={"bed_name": "Twin"},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_room_types_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.get(
        "/properties/00000000-0000-0000-0000-000000000000/rooms/room-types",
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_bed_types_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.get(
        "/properties/00000000-0000-0000-0000-000000000000/rooms/bed-types",
    )
    assert resp.status_code in (401, 403), resp.text


# ────────────────────────────────────────────────────────────────────────────
# Validation — bad payloads rejected before reaching the DB
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_rooms_empty_payload(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms",
        json={},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_rooms_empty_list(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms",
        json={"rooms": []},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_rooms_invalid_base_rate(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms",
        json={
            "rooms": [
                {
                    "room_name": "X",
                    "floor_number": 1,
                    "max_adults": 1,
                    "max_children": 0,
                    "base_rate": "0",
                    "status": "AVAILABLE",
                    "cancellation_policy": "FLEXIBLE",
                    "room_type_id": "00000000-0000-0000-0000-000000000000",
                    "bed_type_id": "00000000-0000-0000-0000-000000000000",
                    "photos": {"cover": None, "gallery": []},
                    "system_amenity_ids": [],
                    "custom_amenities": [],
                }
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_rooms_invalid_max_adults(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms",
        json={
            "rooms": [
                {
                    "room_name": "X",
                    "floor_number": 1,
                    "max_adults": 0,
                    "max_children": 0,
                    "base_rate": "100.00",
                    "status": "AVAILABLE",
                    "cancellation_policy": "FLEXIBLE",
                    "room_type_id": "00000000-0000-0000-0000-000000000000",
                    "bed_type_id": "00000000-0000-0000-0000-000000000000",
                    "photos": {"cover": None, "gallery": []},
                    "system_amenity_ids": [],
                    "custom_amenities": [],
                }
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_rooms_duplicate_names_in_batch(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms",
        json={
            "rooms": [
                {
                    "room_name": "Duplicate",
                    "floor_number": 1,
                    "max_adults": 1,
                    "max_children": 0,
                    "base_rate": "100.00",
                    "status": "AVAILABLE",
                    "cancellation_policy": "FLEXIBLE",
                    "room_type_id": "00000000-0000-0000-0000-000000000000",
                    "bed_type_id": "00000000-0000-0000-0000-000000000000",
                    "photos": {"cover": None, "gallery": []},
                    "system_amenity_ids": [],
                    "custom_amenities": [],
                },
                {
                    "room_name": "Duplicate",
                    "floor_number": 2,
                    "max_adults": 2,
                    "max_children": 1,
                    "base_rate": "200.00",
                    "status": "AVAILABLE",
                    "cancellation_policy": "FLEXIBLE",
                    "room_type_id": "00000000-0000-0000-0000-000000000000",
                    "bed_type_id": "00000000-0000-0000-0000-000000000000",
                    "photos": {"cover": None, "gallery": []},
                    "system_amenity_ids": [],
                    "custom_amenities": [],
                },
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# Room type & bed type creation
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_room_type_success(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms/room-type",
        json=ROOM_TYPE_PAYLOAD,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["room_type_name"] == ROOM_TYPE_PAYLOAD["room_type_name"]
    assert uuid.UUID(data["id"])
    pms_token_store["room_type_id"] = data["id"]


@pytest.mark.asyncio
async def test_create_room_type_duplicate(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms/room-type",
        json=ROOM_TYPE_PAYLOAD,
        headers=headers,
    )
    assert resp.status_code in (400, 409), resp.text


@pytest.mark.asyncio
async def test_create_bed_type_success(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms/bed-type",
        json=BED_TYPE_PAYLOAD,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["bed_name"] == BED_TYPE_PAYLOAD["bed_name"]
    assert uuid.UUID(data["id"])
    pms_token_store["bed_type_id"] = data["id"]


@pytest.mark.asyncio
async def test_create_bed_type_duplicate(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms/bed-type",
        json=BED_TYPE_PAYLOAD,
        headers=headers,
    )
    assert resp.status_code in (400, 409), resp.text


# ────────────────────────────────────────────────────────────────────────────
# Room CRUD
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_rooms_success(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = _room_payload(
        room_type_id=pms_token_store["room_type_id"],
        bed_type_id=pms_token_store["bed_type_id"],
    )
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["success"] is True
    rooms = data["data"]["rooms"]
    assert isinstance(rooms, list)
    assert len(rooms) == 1
    room = rooms[0]
    assert room["room_name"] == "101"
    assert uuid.UUID(room["id"])
    assert uuid.UUID(room["room_type_id"])
    assert uuid.UUID(room["bed_type_id"])
    pms_token_store["room_id"] = room["id"]


@pytest.mark.asyncio
async def test_create_rooms_unknown_property(
    pms_client: AsyncClient, pms_token_store: dict
):
    headers = auth_headers(pms_token_store["access_token"])
    fake_id = "00000000-0000-0000-0000-000000000099"
    payload = _room_payload(
        room_type_id=pms_token_store["room_type_id"],
        bed_type_id=pms_token_store["bed_type_id"],
    )
    resp = await pms_client.post(
        f"/properties/{fake_id}/rooms",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_get_rooms(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/rooms",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    rooms = data["data"]
    assert isinstance(rooms, list)
    assert len(rooms) >= 1
    for field in (
        "id", "room_name", "floor_number", "max_adults", "max_children",
        "base_rate", "status", "cancellation_policy",
        "room_type_id", "bed_type_id",
        "photos", "system_amenity_ids", "custom_amenities",
    ):
        assert field in rooms[0], f"Missing field: {field}"


@pytest.mark.asyncio
async def test_get_room_by_id(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    room_id = pms_token_store["room_id"]
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/rooms/{room_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    room = data["data"]
    assert room["id"] == room_id
    assert room["room_name"] == "101"


@pytest.mark.asyncio
async def test_get_room_by_id_not_found(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    fake_id = "00000000-0000-0000-0000-000000000077"
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/rooms/{fake_id}",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_get_room_types(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/rooms/room-types",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    types = data["data"]
    assert isinstance(types, list)
    names = [t["room_type_name"] for t in types]
    assert ROOM_TYPE_PAYLOAD["room_type_name"] in names


@pytest.mark.asyncio
async def test_get_bed_types(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/rooms/bed-types",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    types = data["data"]
    assert isinstance(types, list)
    names = [t["bed_name"] for t in types]
    assert BED_TYPE_PAYLOAD["bed_name"] in names


# ────────────────────────────────────────────────────────────────────────────
# Update & Delete
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_room_success(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    room_id = pms_token_store["room_id"]
    update_payload = {
        "room_name": "101-Updated",
        "floor_number": 2,
        "max_adults": 3,
        "max_children": 2,
        "base_rate": "175.00",
        "status": "AVAILABLE",
        "cancellation_policy": "MODERATE",
        "room_type_id": pms_token_store["room_type_id"],
        "bed_type_id": pms_token_store["bed_type_id"],
        "photos": {"cover": None, "gallery": []},
        "system_amenity_ids": [],
        "custom_amenities": [],
    }
    resp = await pms_client.patch(
        f"/properties/{pms_property_id}/rooms/{room_id}",
        json=update_payload,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    updated = data["data"]
    assert updated["room_name"] == "101-Updated"
    assert updated["floor_number"] == 2
    assert updated["max_adults"] == 3


@pytest.mark.asyncio
async def test_update_room_not_found(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    fake_id = "00000000-0000-0000-0000-000000000088"
    resp = await pms_client.patch(
        f"/properties/{pms_property_id}/rooms/{fake_id}",
        json={"room_name": "Ghost Room"},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_delete_room(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = _room_payload(
        room_type_id=pms_token_store["room_type_id"],
        bed_type_id=pms_token_store["bed_type_id"],
        room_name="ToDelete",
    )
    create_resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms",
        json=payload,
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    room_id = create_resp.json()["data"]["rooms"][0]["id"]

    resp = await pms_client.delete(
        f"/properties/{pms_property_id}/rooms/{room_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_delete_room_not_found(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    fake_id = "00000000-0000-0000-0000-000000000066"
    resp = await pms_client.delete(
        f"/properties/{pms_property_id}/rooms/{fake_id}",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# Edge cases
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_room_type_name_too_long(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms/room-type",
        json={"room_type_name": "A" * 101},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# Room list filtering & pagination
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_rooms_filter_by_status(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/rooms",
        params={"status": "AVAILABLE"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert all(
        room["status"] == "AVAILABLE" for room in body["data"]
    ), body["data"]


@pytest.mark.asyncio
async def test_get_rooms_filter_by_floor(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/rooms",
        params={"floor_number": 1},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert all(room["floor_number"] == 1 for room in body["data"])


@pytest.mark.asyncio
async def test_get_rooms_invalid_status(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/rooms",
        params={"status": "BOGUS"},
        headers=headers,
    )
    assert resp.status_code in (400, 422), resp.text


@pytest.mark.asyncio
async def test_get_rooms_meta_pagination(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/rooms",
        params={"skip": 0, "limit": 1},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    meta = body["meta"]
    assert "total" in meta and "skip" in meta and "limit" in meta
    assert meta["skip"] == 0 and meta["limit"] == 1
    assert isinstance(meta["has_more"], bool)
    assert len(body["data"]) <= 1


# ────────────────────────────────────────────────────────────────────────────
# Public available-rooms endpoint (no auth required)
# ────────────────────────────────────────────────────────────────────────────

def _future_date(days: int) -> str:
    from datetime import date, timedelta
    return (date.today() + timedelta(days=days)).isoformat()


@pytest.mark.asyncio
async def test_available_rooms_public_success(
    async_client: AsyncClient, mocker
):
    from app.modules.pms.dependencies import get_room_service
    from app.modules.pms.services.room_services import RoomService
    from unittest.mock import AsyncMock
    from app.main import app

    available_payload = {
        "id": str(uuid.uuid4()),
        "room_name": "101",
        "room_type": "Deluxe Suite",
        "bed_type": "King",
        "base_rate": "150.00",
        "photos": {"cover": None, "gallery": []},
        "max_adults": 2,
        "max_children": 1,
        "status": "AVAILABLE",
        "floor_number": 1,
        "cancellation_policy": "FLEXIBLE",
        "cancellation_title": "Flexible Cancellation",
        "cancellation_description": "Full refund",
        "system_amenities": [],
        "custom_amenities": [],
    }
    mock = AsyncMock(spec=RoomService)
    mock.get_available_rooms.return_value = [available_payload]
    app.dependency_overrides[get_room_service] = lambda: mock
    resp = await async_client.get(
        f"/properties/{uuid.uuid4()}/rooms/available-rooms",
        params={
            "checkin_date": _future_date(5),
            "checkout_date": _future_date(7),
        },
    )
    app.dependency_overrides.pop(get_room_service, None)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"][0]["status"] == "AVAILABLE"


@pytest.mark.asyncio
async def test_public_available_rooms_inverted_dates(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/rooms/available-rooms",
        params={
            "checkin_date": _future_date(7),
            "checkout_date": _future_date(5),
        },
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_public_available_rooms_past_checkin(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/rooms/available-rooms",
        params={
            "checkin_date": _future_date(-5),
            "checkout_date": _future_date(2),
        },
    )
    assert resp.status_code == 400, resp.text


# ────────────────────────────────────────────────────────────────────────────
# No-tenant admin can't list/create rooms (verify_tenant → 400)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_rooms_no_tenant(async_client: AsyncClient):
    from .test_image_routers import _register_no_tenant_admin

    token = await _register_no_tenant_admin(async_client)
    headers = auth_headers(token)
    resp = await async_client.get(
        "/properties/00000000-0000-0000-0000-000000000000/rooms",
        headers=headers,
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_create_rooms_no_tenant(async_client: AsyncClient):
    from .test_image_routers import _register_no_tenant_admin

    token = await _register_no_tenant_admin(async_client)
    headers = auth_headers(token)
    valid = _room_payload(
        room_type_id=str(uuid.uuid4()), bed_type_id=str(uuid.uuid4()), room_name="NoTenant"
    )
    resp = await async_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/rooms",
        json=valid,
        headers=headers,
    )
    assert resp.status_code == 400, resp.text


# ────────────────────────────────────────────────────────────────────────────
# CUSTOM cancellation policy requires fields
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_rooms_custom_policy_without_fields(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = _room_payload(
        room_type_id=pms_token_store["room_type_id"],
        bed_type_id=pms_token_store["bed_type_id"],
        room_name="CustomNoFields",
        cancellation_policy="CUSTOM",
    )
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_rooms_custom_policy_with_fields(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = _room_payload(
        room_type_id=pms_token_store["room_type_id"],
        bed_type_id=pms_token_store["bed_type_id"],
        room_name="CustomWithFields",
        cancellation_policy="CUSTOM",
        cancellation_title="Custom Title",
        cancellation_description="Custom Description",
    )
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/rooms",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    room = resp.json()["data"]["rooms"][0]
    assert room["cancellation_title"] == "Custom Title"


@pytest.mark.asyncio
async def test_create_rooms_duplicate_room_name_across_requests(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = _room_payload(
        room_type_id=pms_token_store["room_type_id"],
        bed_type_id=pms_token_store["bed_type_id"],
        room_name="UniqueRoomA",
    )
    first = await pms_client.post(
        f"/properties/{pms_property_id}/rooms",
        json=payload,
        headers=headers,
    )
    assert first.status_code == 201, first.text

    second = await pms_client.post(
        f"/properties/{pms_property_id}/rooms",
        json=payload,
        headers=headers,
    )
    assert second.status_code in (400, 409), second.text
