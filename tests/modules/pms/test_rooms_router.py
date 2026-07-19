"""
Tests for /pms/properties/{property_id}/rooms/* endpoints.

Depends on `pms_client` + `pms_token_store` (from pms/conftest.py),
which already holds an access_token and property_id.
"""
import pytest
from httpx import AsyncClient


# ─── helpers ────────────────────────────────────────────────────────────────

def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


VALID_ROOMS_PAYLOAD = {
    "rooms": [
        {
            "room_name": "101",
            "floor_number": 1,
            "max_adults": 2,
            "max_children": 1,
            "base_rate": "150.00",
            "status": "AVAILABLE",
            "cancellation_policy": "FLEXIBLE",
            "cancellation_notes": "Free cancellation up to 24h before.",
            "room_type": {"room_type_name": "Standard", "is_default": False},
            "bed_type": {"bed_name": "King", "is_default": False},
            "photos": ["https://example.com/room101.jpg"],
            "amenities": [],
        },
        {
            "room_name": "102",
            "floor_number": 1,
            "max_adults": 2,
            "max_children": 0,
            "base_rate": "200.00",
            "status": "AVAILABLE",
            "cancellation_policy": "STRICT",
            "cancellation_notes": None,
            "room_type": {"room_type_name": "Deluxe", "is_default": False},
            "bed_type": {"bed_name": "Queen", "is_default": False},
            "photos": [],
            "amenities": [],
        },
    ]
}

@pytest.fixture(autouse=True)
async def setup_property(pms_property_id):
    pass

# ────────────────────────────────────────────────────────────────────────────
# POST /pms/properties/{property_id}/rooms — unauthenticated
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_rooms_unauthenticated(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["property_id"]
    resp = await pms_client.post(
        f"/pms/properties/{prop_id}/rooms", json=VALID_ROOMS_PAYLOAD
    )
    assert resp.status_code in (401, 403), resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/properties/{property_id}/rooms — success (batch)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_rooms(pms_client: AsyncClient, pms_token_store: dict):
    prop_id = pms_token_store["property_id"]
    resp = await pms_client.post(
        f"/pms/properties/{prop_id}/rooms",
        json=VALID_ROOMS_PAYLOAD,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["success"] is True
    rooms = data["data"]
    assert isinstance(rooms, list)
    assert len(rooms) == 2

    # validate shape of first room response
    first = rooms[0]
    assert "id" in first
    assert "room" in first
    room_body = first["room"]
    assert room_body["room_name"] in ("101", "102")
    assert "room_type" in room_body
    assert "bed_type" in room_body

    # persist first room id for update/delete tests
    pms_token_store["room_id"] = rooms[0]["id"]


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/properties/{property_id}/rooms — empty list → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_rooms_empty_list(pms_client: AsyncClient, pms_token_store: dict):
    prop_id = pms_token_store["property_id"]
    resp = await pms_client.post(
        f"/pms/properties/{prop_id}/rooms",
        json={"rooms": []},
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/properties/{property_id}/rooms — invalid base_rate (0) → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_room_invalid_base_rate(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["property_id"]
    bad_payload = {
        "rooms": [
            {
                **VALID_ROOMS_PAYLOAD["rooms"][0],
                "room_name": "103",
                "base_rate": "0",          # must be > 0
            }
        ]
    }
    resp = await pms_client.post(
        f"/pms/properties/{prop_id}/rooms",
        json=bad_payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/properties/{property_id}/rooms — bad max_adults (0) → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_room_invalid_max_adults(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["property_id"]
    bad_payload = {
        "rooms": [
            {
                **VALID_ROOMS_PAYLOAD["rooms"][0],
                "room_name": "104",
                "max_adults": 0,           # min is 1
            }
        ]
    }
    resp = await pms_client.post(
        f"/pms/properties/{prop_id}/rooms",
        json=bad_payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/properties/{property_id}/rooms — unknown property → 404
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_rooms_unknown_property(
    pms_client: AsyncClient, pms_token_store: dict
):
    fake_id = "00000000-0000-0000-0000-000000000099"
    resp = await pms_client.post(
        f"/pms/properties/{fake_id}/rooms",
        json=VALID_ROOMS_PAYLOAD,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# GET /pms/properties/{property_id}/rooms — list
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_rooms(pms_client: AsyncClient, pms_token_store: dict):
    prop_id = pms_token_store["property_id"]
    resp = await pms_client.get(
        f"/pms/properties/{prop_id}/rooms",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    rooms = data["data"]
    assert isinstance(rooms, list)
    assert len(rooms) >= 2

    # Validate RoomsDetailResponse shape
    room = rooms[0]
    for field in (
        "id", "room_name", "floor_number", "max_adults", "max_children",
        "base_rate", "status", "cancellation_policy", "room_type", "bed_type",
        "photos", "amenities",
    ):
        assert field in room, f"Missing field: {field}"


# ────────────────────────────────────────────────────────────────────────────
# PATCH /pms/properties/{property_id}/rooms/{room_id} — success
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_room(pms_client: AsyncClient, pms_token_store: dict):
    prop_id = pms_token_store["property_id"]
    room_id = pms_token_store["room_id"]
    update_payload = {
        "room_name": "101-Updated",
        "floor_number": 2,
        "max_adults": 3,
        "max_children": 2,
        "base_rate": "175.00",
        "status": "AVAILABLE",
        "cancellation_policy": "MODERATE",
        "cancellation_notes": "Updated notes",
        "room_type": {"room_type_name": "Standard", "is_default": False},
        "bed_type": {"bed_name": "King", "is_default": False},
        "photos": [],
        "amenities": [],
    }
    resp = await pms_client.patch(
        f"/pms/properties/{prop_id}/rooms/{room_id}",
        json=update_payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    updated = data["data"]
    assert updated["room_name"] == "101-Updated"
    assert updated["floor_number"] == 2
    assert updated["max_adults"] == 3


# ────────────────────────────────────────────────────────────────────────────
# PATCH /pms/properties/{property_id}/rooms/{room_id} — unknown room → 404
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_room_not_found(pms_client: AsyncClient, pms_token_store: dict):
    prop_id = pms_token_store["property_id"]
    fake_room_id = "00000000-0000-0000-0000-000000000088"
    update_payload = {
        "room_name": "Ghost Room",
        "floor_number": 1,
        "max_adults": 2,
        "max_children": 0,
        "base_rate": "100.00",
        "status": "AVAILABLE",
        "cancellation_policy": "FLEXIBLE",
        "cancellation_notes": None,
        "room_type": {"room_type_name": "Standard", "is_default": False},
        "bed_type": {"bed_name": "King", "is_default": False},
        "photos": [],
        "amenities": [],
    }
    resp = await pms_client.patch(
        f"/pms/properties/{prop_id}/rooms/{fake_room_id}",
        json=update_payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# DELETE /pms/properties/{property_id}/rooms/{room_id} — success
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_room(pms_client: AsyncClient, pms_token_store: dict):
    prop_id = pms_token_store["property_id"]

    # Create a disposable room to delete
    disp_payload = {
        "rooms": [
            {
                **VALID_ROOMS_PAYLOAD["rooms"][0],
                "room_name": "999",
            }
        ]
    }
    create_resp = await pms_client.post(
        f"/pms/properties/{prop_id}/rooms",
        json=disp_payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert create_resp.status_code == 201, create_resp.text
    room_to_delete = create_resp.json()["data"][0]["id"]

    resp = await pms_client.delete(
        f"/pms/properties/{prop_id}/rooms/{room_to_delete}",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True


# ────────────────────────────────────────────────────────────────────────────
# DELETE /pms/properties/{property_id}/rooms/{room_id} — wrong room id → 404
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_room_not_found(pms_client: AsyncClient, pms_token_store: dict):
    prop_id = pms_token_store["property_id"]
    fake_room_id = "00000000-0000-0000-0000-000000000077"
    resp = await pms_client.delete(
        f"/pms/properties/{prop_id}/rooms/{fake_room_id}",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text
