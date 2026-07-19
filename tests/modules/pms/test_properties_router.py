"""
Tests for /pms/properties/* endpoints.

All tests share `pms_client` (authenticated admin with tenant) and
`pms_token_store` from the PMS-level conftest.py.

Execution order relies on declaration order + shared pms_token_store
to pass property_id to later tests.
"""
import pytest
from httpx import AsyncClient


# ─── helpers ────────────────────────────────────────────────────────────────

def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


VALID_PROPERTY_PAYLOAD = {
    "name": "Ocean View Hotel",
    "type": "HOTEL",
    "description": "A beautiful hotel with ocean views.",
    "country": "New Zealand",
    "state": "Auckland",
    "city": "Auckland City",
    "zip_code": "1010",
    "address": "123 Ocean Drive",
    "latitude": "-36.848461",
    "longitude": "174.763336",
    "hotel_detail": {
        "check_in_time_from": "2:00 PM",
        "check_in_time_to": "6:00 PM",
        "check_out_time_from": "9:00 AM",
        "check_out_time_to": "11:00 AM",
        "total_rooms": 20,
        "year_built": 2010,
        "number_of_floors": 5,
    },
    "amenities": [
        {"name": "Free WiFi", "is_default": False},
        {"name": "Swimming Pool", "is_default": False},
    ],
    "photo_urls": [
        "https://example.com/photo1.jpg",
        "https://example.com/photo2.jpg",
    ],
}


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/properties/ — unauthenticated
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_property_unauthenticated(pms_client: AsyncClient):
    """Without token, should get 401/403."""
    resp = await pms_client.post("/pms/properties/", json=VALID_PROPERTY_PAYLOAD)
    assert resp.status_code in (401, 403), resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/properties/ — success
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_property(pms_client: AsyncClient, pms_token_store: dict):
    resp = await pms_client.post(
        "/pms/properties/",
        json=VALID_PROPERTY_PAYLOAD,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["success"] is True

    prop = data["data"]
    assert prop["name"] == "Ocean View Hotel"
    assert prop["type"] == "HOTEL"
    assert prop["country"] == "New Zealand"
    assert "id" in prop
    assert "hotel_detail" in prop
    assert len(prop["amenities"]) == 2
    assert len(prop["photos"]) == 2

    # persist for subsequent tests
    pms_token_store["property_id"] = prop["id"]


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/properties/ — duplicate amenities → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_property_duplicate_amenities(
    pms_client: AsyncClient, pms_token_store: dict
):
    bad_payload = {**VALID_PROPERTY_PAYLOAD, "name": "Another Hotel"}
    bad_payload["amenities"] = [
        {"name": "Free WiFi", "is_default": False},
        {"name": "free wifi", "is_default": False},   # case-insensitive duplicate
    ]
    resp = await pms_client.post(
        "/pms/properties/",
        json=bad_payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/properties/ — invalid check-in time order → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_property_invalid_checkin_times(
    pms_client: AsyncClient, pms_token_store: dict
):
    bad_payload = {
        **VALID_PROPERTY_PAYLOAD,
        "name": "Bad Time Hotel",
        "hotel_detail": {
            **VALID_PROPERTY_PAYLOAD["hotel_detail"],
            "check_in_time_from": "6:00 PM",   # from AFTER to — invalid
            "check_in_time_to": "2:00 PM",
        },
    }
    resp = await pms_client.post(
        "/pms/properties/",
        json=bad_payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# GET /pms/properties/ — list all
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_all_properties(pms_client: AsyncClient, pms_token_store: dict):
    resp = await pms_client.get(
        "/pms/properties/",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 1


# ────────────────────────────────────────────────────────────────────────────
# GET /pms/properties/amenities — default amenities
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_all_amenities(pms_client: AsyncClient, pms_token_store: dict):
    resp = await pms_client.get(
        "/pms/properties/amenities",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


# ────────────────────────────────────────────────────────────────────────────
# GET /pms/properties/{property_id} — by ID
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_property_by_id(pms_client: AsyncClient, pms_token_store: dict):
    prop_id = pms_token_store["property_id"]
    resp = await pms_client.get(
        f"/pms/properties/{prop_id}",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["id"] == prop_id
    assert data["data"]["name"] == "Ocean View Hotel"


# ────────────────────────────────────────────────────────────────────────────
# GET /pms/properties/{property_id} — wrong UUID → 404
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_property_not_found(pms_client: AsyncClient, pms_token_store: dict):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await pms_client.get(
        f"/pms/properties/{fake_id}",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# PATCH /pms/properties/{property_id} — success
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_property(pms_client: AsyncClient, pms_token_store: dict):
    prop_id = pms_token_store["property_id"]
    updated_payload = {
        **VALID_PROPERTY_PAYLOAD,
        "name": "Ocean View Hotel Updated",
        "description": "Updated description.",
    }
    resp = await pms_client.patch(
        f"/pms/properties/{prop_id}",
        json=updated_payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Ocean View Hotel Updated"
    assert data["data"]["description"] == "Updated description."


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/properties/{property_id}/activation — toggle active
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toggle_property_activation(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["property_id"]
    resp = await pms_client.post(
        f"/pms/properties/{prop_id}/activation",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True


# ────────────────────────────────────────────────────────────────────────────
# DELETE /pms/properties/{property_id}
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_property(pms_client: AsyncClient, pms_token_store: dict):
    # First create a disposable property so we don't destroy the one used by room tests
    resp = await pms_client.post(
        "/pms/properties/",
        json={**VALID_PROPERTY_PAYLOAD, "name": "Disposable Hotel"},
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 201, resp.text
    delete_id = resp.json()["data"]["id"]

    resp = await pms_client.delete(
        f"/pms/properties/{delete_id}",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True


# ────────────────────────────────────────────────────────────────────────────
# DELETE /pms/properties/{property_id} — wrong UUID → 404
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_property_not_found(
    pms_client: AsyncClient, pms_token_store: dict
):
    fake_id = "00000000-0000-0000-0000-000000000001"
    resp = await pms_client.delete(
        f"/pms/properties/{fake_id}",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text
