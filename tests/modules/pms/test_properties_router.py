import uuid
from unittest.mock import AsyncMock
from httpx import AsyncClient
import pytest
from app.main import app
from app.Images.image_services import ImageService

CLOUDINARY_BASE = "https://res.cloudinary.com/drahdqd63/image/upload/"

GENERAL_INFO_PAYLOAD = {
    "name": "Test Hotel",
    "type": "HOTEL",
    "description": "A test hotel",
    "phone_number": "1234567890",
    "email": "hotel@test.com",
    "total_rooms": 10,
    "number_of_floors": 3,
    "year_built": 2000,
}

LOCATION_PAYLOAD = {
    "country": "New Zealand",
    "state": "Auckland",
    "city": "Auckland City",
    "zip_code": "1010",
    "address": "123 Test St",
    "latitude": "-36.848461",
    "longitude": "174.763336",
}

PHOTOS_AMENITIES_PAYLOAD = {
    "photos": {
        "cover": f"{CLOUDINARY_BASE}cover.jpg",
        "gallery": [f"{CLOUDINARY_BASE}gallery1.jpg"],
    },
    "amenities": {
        "system_amenity_ids": [],
        "custom_amenities": [],
    },
}

LOCALIZATION_PAYLOAD = {
    "currency": "USD",
    "timezone": "UTC",
    "language": "English",
    "always_allow_check_in_out": True,
}

BRAND_VISUAL_PAYLOAD = {
    "brand_logo_url": f"{CLOUDINARY_BASE}logo.jpg",
    "brand_color": "#FF5733",
}


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_property(client: AsyncClient, store: dict) -> str:
    headers = auth_headers(store["access_token"])
    resp = await client.post(
        "/properties/general-information", json=GENERAL_INFO_PAYLOAD, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_unique_property(client: AsyncClient, store: dict, name: str) -> str:
    headers = auth_headers(store["access_token"])
    payload = {**GENERAL_INFO_PAYLOAD, "name": name}
    resp = await client.post(
        "/properties/general-information", json=payload, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


# ────────────────────────────────────────────────────────────────────────────
# Unauthenticated — all endpoints without token → 401/403
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_general_info_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.post(
        "/properties/general-information", json=GENERAL_INFO_PAYLOAD
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_properties_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.get("/properties/")
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_property_by_id_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.get("/properties/00000000-0000-0000-0000-000000000000")
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_amenities_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.get("/properties/amenities")
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_delete_property_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.delete("/properties/00000000-0000-0000-0000-000000000000")
    assert resp.status_code in (401, 403), resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /properties/general-information — validation → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_general_info_name_too_short(
    pms_client: AsyncClient, pms_token_store: dict
):
    payload = {**GENERAL_INFO_PAYLOAD, "name": "A"}
    resp = await pms_client.post(
        "/properties/general-information",
        json=payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_general_info_name_too_long(
    pms_client: AsyncClient, pms_token_store: dict
):
    payload = {**GENERAL_INFO_PAYLOAD, "name": "A" * 256}
    resp = await pms_client.post(
        "/properties/general-information",
        json=payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_general_info_invalid_phone(
    pms_client: AsyncClient, pms_token_store: dict
):
    payload = {**GENERAL_INFO_PAYLOAD, "phone_number": "invalid"}
    resp = await pms_client.post(
        "/properties/general-information",
        json=payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_general_info_invalid_email(
    pms_client: AsyncClient, pms_token_store: dict
):
    payload = {**GENERAL_INFO_PAYLOAD, "email": "not-an-email"}
    resp = await pms_client.post(
        "/properties/general-information",
        json=payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_general_info_missing_required(
    pms_client: AsyncClient, pms_token_store: dict
):
    resp = await pms_client.post(
        "/properties/general-information",
        json={},
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /properties/general-information — success + duplicate
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_general_info_success(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = await _create_property(pms_client, pms_token_store)
    uuid.UUID(prop_id)
    pms_token_store["test_property_id"] = prop_id


@pytest.mark.asyncio
async def test_create_general_info_duplicate_name(
    pms_client: AsyncClient, pms_token_store: dict
):
    resp = await pms_client.post(
        "/properties/general-information",
        json=GENERAL_INFO_PAYLOAD,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code in (400, 409), resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /properties/{id}/create-location
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_location_success(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["test_property_id"]
    resp = await pms_client.post(
        f"/properties/{prop_id}/create-location",
        json=LOCATION_PAYLOAD,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["country"] == "New Zealand"


@pytest.mark.asyncio
async def test_create_location_property_not_found(
    pms_client: AsyncClient, pms_token_store: dict
):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await pms_client.post(
        f"/properties/{fake_id}/create-location",
        json=LOCATION_PAYLOAD,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_create_location_invalid_country(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["test_property_id"]
    payload = {**LOCATION_PAYLOAD, "country": "X"}
    resp = await pms_client.post(
        f"/properties/{prop_id}/create-location",
        json=payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /properties/{id}/create-photos-and-amenities
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_photos_and_amenities_success(
    pms_client: AsyncClient, pms_token_store: dict, mocker
):
    mocker.patch.object(ImageService, "promote_temp_images", return_value=[
        f"{CLOUDINARY_BASE}cover.jpg",
        f"{CLOUDINARY_BASE}gallery1.jpg",
    ])
    prop_id = pms_token_store["test_property_id"]
    resp = await pms_client.post(
        f"/properties/{prop_id}/create-photos-and-amenities",
        json=PHOTOS_AMENITIES_PAYLOAD,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["photos"]["cover"] == f"{CLOUDINARY_BASE}cover.jpg"


@pytest.mark.asyncio
async def test_create_photos_and_amenities_property_not_found(
    pms_client: AsyncClient, pms_token_store: dict
):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await pms_client.post(
        f"/properties/{fake_id}/create-photos-and-amenities",
        json=PHOTOS_AMENITIES_PAYLOAD,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_create_photos_and_amenities_duplicate_custom_amenity(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["test_property_id"]
    payload = {
        "photos": {
            "cover": f"{CLOUDINARY_BASE}cover.jpg",
            "gallery": [],
        },
        "amenities": {
            "system_amenity_ids": [],
            "custom_amenities": [
                {"name": "Pool", "icon": "fa-pool"},
                {"name": "pool", "icon": "fa-pool"},
            ],
        },
    }
    resp = await pms_client.post(
        f"/properties/{prop_id}/create-photos-and-amenities",
        json=payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code in (400, 409), resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /properties/{id}/create-localization
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_localization_success(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["test_property_id"]
    resp = await pms_client.post(
        f"/properties/{prop_id}/create-localization",
        json=LOCALIZATION_PAYLOAD,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["currency"] == "USD"


@pytest.mark.asyncio
async def test_create_localization_property_not_found(
    pms_client: AsyncClient, pms_token_store: dict
):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await pms_client.post(
        f"/properties/{fake_id}/create-localization",
        json=LOCALIZATION_PAYLOAD,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_create_localization_invalid_check_in_out(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["test_property_id"]
    payload = {
        "always_allow_check_in_out": True,
        "check_in_time": "2:00 PM",
        "check_out_time": "11:00 AM",
    }
    resp = await pms_client.post(
        f"/properties/{prop_id}/create-localization",
        json=payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /properties/{id}/create-brand-visual
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_brand_visual_success(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["test_property_id"]
    resp = await pms_client.post(
        f"/properties/{prop_id}/create-brand-visual",
        json=BRAND_VISUAL_PAYLOAD,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_create_brand_visual_property_not_found(
    pms_client: AsyncClient, pms_token_store: dict
):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await pms_client.post(
        f"/properties/{fake_id}/create-brand-visual",
        json=BRAND_VISUAL_PAYLOAD,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# GET /properties/ — list
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_properties_list(
    pms_client: AsyncClient, pms_token_store: dict
):
    resp = await pms_client.get(
        "/properties/",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["meta"]["total"] >= 1
    assert len(body["data"]["properties"]) >= 1


# ────────────────────────────────────────────────────────────────────────────
# GET /properties/amenities
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_amenities(
    pms_client: AsyncClient, pms_token_store: dict
):
    resp = await pms_client.get(
        "/properties/amenities",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"]["amenities"], list)
    assert data["data"]["total_count"] >= 0


# ────────────────────────────────────────────────────────────────────────────
# GET /properties/{property_id} — by ID
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_property_by_id(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["test_property_id"]
    resp = await pms_client.get(
        f"/properties/{prop_id}",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["id"] == prop_id
    assert data["data"]["name"] == GENERAL_INFO_PAYLOAD["name"]


@pytest.mark.asyncio
async def test_get_property_by_id_not_found(
    pms_client: AsyncClient, pms_token_store: dict
):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await pms_client.get(
        f"/properties/{fake_id}",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /properties/{id}/toggle-property-activation
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_toggle_property_activation(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["test_property_id"]
    resp = await pms_client.post(
        f"/properties/{prop_id}/toggle-property-activation",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_toggle_property_activation_not_found(
    pms_client: AsyncClient, pms_token_store: dict
):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await pms_client.post(
        f"/properties/{fake_id}/toggle-property-activation",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# DELETE /properties/{property_id}
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_property(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["test_property_id"]
    resp = await pms_client.delete(
        f"/properties/{prop_id}",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_delete_property_not_found(
    pms_client: AsyncClient, pms_token_store: dict
):
    fake_id = "00000000-0000-0000-0000-000000000001"
    resp = await pms_client.delete(
        f"/properties/{fake_id}",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# PATCH /properties/{property_id}
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_property_success(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = await _create_unique_property(pms_client, pms_token_store, "Update Hotel")
    resp = await pms_client.patch(
        f"/properties/{prop_id}",
        json={"name": "Updated Hotel"},
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Updated Hotel"


@pytest.mark.asyncio
async def test_update_property_not_found(
    pms_client: AsyncClient, pms_token_store: dict
):
    fake_id = "00000000-0000-0000-0000-000000000002"
    resp = await pms_client.patch(
        f"/properties/{fake_id}",
        json={"name": "Ghost"},
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_update_property_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.patch(
        "/properties/00000000-0000-0000-0000-000000000000",
        json={"name": "Hacked"},
    )
    assert resp.status_code in (401, 403), resp.text


# ────────────────────────────────────────────────────────────────────────────
# GET /properties/{property_id}/public  (no auth required)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_specific_public_property(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = await _create_unique_property(pms_client, pms_token_store, "Public Hotel")
    headers = auth_headers(pms_token_store["access_token"])
    act_resp = await pms_client.post(
        f"/properties/{prop_id}/toggle-property-activation", headers=headers
    )
    assert act_resp.status_code == 200, act_resp.text
    resp = await pms_client.get(f"/properties/{prop_id}/public")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["id"] == prop_id


@pytest.mark.asyncio
async def test_get_specific_public_property_not_found(pms_client: AsyncClient):
    fake_id = "00000000-0000-0000-0000-000000000003"
    resp = await pms_client.get(f"/properties/{fake_id}/public")
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# GET /properties/{property_id}/number-of-floors
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_number_of_floors(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = await _create_unique_property(pms_client, pms_token_store, "Floors Hotel")
    resp = await pms_client.get(
        f"/properties/{prop_id}/number-of-floors",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"]["number_of_floors"], int)


@pytest.mark.asyncio
async def test_get_number_of_floors_not_found(
    pms_client: AsyncClient, pms_token_store: dict
):
    fake_id = "00000000-0000-0000-0000-000000000004"
    resp = await pms_client.get(
        f"/properties/{fake_id}/number-of-floors",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# GET /properties/{property_id}/bookings (empty list for a fresh property)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_property_bookings_empty(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = await _create_unique_property(pms_client, pms_token_store, "Bookings Hotel")
    resp = await pms_client.get(
        f"/properties/{prop_id}/bookings",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_get_property_bookings_not_found(
    pms_client: AsyncClient, pms_token_store: dict
):
    fake_id = "00000000-0000-0000-0000-000000000005"
    resp = await pms_client.get(
        f"/properties/{fake_id}/bookings",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# GET /properties/ — pagination meta
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_properties_pagination(
    pms_client: AsyncClient, pms_token_store: dict
):
    resp = await pms_client.get(
        "/properties/",
        params={"skip": 0, "limit": 1},
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    meta = body["meta"]
    assert meta["skip"] == 0 and meta["limit"] == 1
    assert isinstance(meta["has_more"], bool)
    assert len(body["data"]["properties"]) <= 1


@pytest.mark.asyncio
async def test_get_properties_invalid_limit(
    pms_client: AsyncClient, pms_token_store: dict
):
    resp = await pms_client.get(
        "/properties/",
        params={"limit": 0},
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text
