"""
Tests for /properties/{property_id}/special-offers/* endpoints.

Depends on `pms_client` + `pms_token_store` (from pms/conftest.py),
which already holds an access_token and property_id.
"""
from datetime import date, timedelta
import uuid
import pytest
from httpx import AsyncClient


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _future_date(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


VALID_OFFER = {
    "title": "Early Bird 10%",
    "description": "Book in advance and save.",
    "discount_percentage": 10.0,
    "start_date": _future_date(5),
    "end_date": _future_date(20),
    "is_active": True,
    "is_custom": False,
}


# ────────────────────────────────────────────────────────────────────────────
# Unauthenticated — all endpoints without token → 401/403
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_offers_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/special-offers/",
        json={"offers": [VALID_OFFER]},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_offers_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.get(
        "/properties/00000000-0000-0000-0000-000000000000/special-offers/",
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_offer_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.get(
        "/properties/00000000-0000-0000-0000-000000000000/special-offers/00000000-0000-0000-0000-000000000000",
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_update_offer_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.patch(
        "/properties/00000000-0000-0000-0000-000000000000/special-offers/00000000-0000-0000-0000-000000000000",
        json={"title": "Hacked"},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_delete_offer_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.delete(
        "/properties/00000000-0000-0000-0000-000000000000/special-offers/00000000-0000-0000-0000-000000000000",
    )
    assert resp.status_code in (401, 403), resp.text


# ────────────────────────────────────────────────────────────────────────────
# Validation — bad payloads rejected before reaching the DB
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_offers_empty_list(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/special-offers/",
        json={"offers": []},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["data"] == []


@pytest.mark.asyncio
async def test_create_offer_past_start_date(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        "offers": [
            {
                **VALID_OFFER,
                "title": "Past Deal",
                "start_date": _future_date(-10),
                "end_date": _future_date(5),
            }
        ]
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/special-offers/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_offer_start_after_end(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        "offers": [
            {
                **VALID_OFFER,
                "title": "Bad Chronology",
                "start_date": _future_date(10),
                "end_date": _future_date(5),
            }
        ]
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/special-offers/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_offer_duplicate_titles_in_batch(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        "offers": [
            {
                **VALID_OFFER,
                "title": "Same Title",
            },
            {
                **VALID_OFFER,
                "title": "same title",
            },
        ]
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/special-offers/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_offer_invalid_discount(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        "offers": [
            {
                **VALID_OFFER,
                "title": "Too Good",
                "discount_percentage": 150.0,
            }
        ]
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/special-offers/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_offer_title_too_short(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        "offers": [
            {
                **VALID_OFFER,
                "title": "A",
            }
        ]
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/special-offers/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# Create success
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_offers_success(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        "offers": [
            VALID_OFFER,
            {
                "title": "Weekend Special 5%",
                "discount_percentage": 5.0,
                "start_date": _future_date(2),
                "end_date": _future_date(10),
                "is_active": False,
                "is_custom": True,
            },
        ]
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/special-offers/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["success"] is True
    offers = data["data"]
    assert isinstance(offers, list)
    assert len(offers) == 2

    for offer in offers:
        for field in (
            "id", "property_id", "title", "discount_percentage",
            "start_date", "end_date", "is_active", "is_custom",
            "created_at", "updated_at",
        ):
            assert field in offer, f"Missing field: {field}"
        assert offer["property_id"] == pms_property_id

    pms_token_store["offer_id"] = offers[0]["id"]


@pytest.mark.asyncio
async def test_create_offers_duplicate_title_db(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        "offers": [
            {
                **VALID_OFFER,
                "title": "Early Bird 10%",
            }
        ]
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/special-offers/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code in (400, 409), resp.text


# ────────────────────────────────────────────────────────────────────────────
# Read
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_offers(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/special-offers/",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 2


@pytest.mark.asyncio
async def test_get_offer_by_id(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    offer_id = pms_token_store["offer_id"]
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/special-offers/{offer_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    offer = data["data"]
    assert offer["id"] == offer_id
    assert offer["title"] == VALID_OFFER["title"]


@pytest.mark.asyncio
async def test_get_offer_by_id_not_found(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    fake_id = "00000000-0000-0000-0000-000000000055"
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/special-offers/{fake_id}",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# Update
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_offer_success(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    offer_id = pms_token_store["offer_id"]
    update_payload = {
        "title": "Early Bird 10% Updated",
        "description": "Updated offer description.",
        "discount_percentage": 12.0,
        "start_date": _future_date(6),
        "end_date": _future_date(22),
        "is_active": True,
    }
    resp = await pms_client.patch(
        f"/properties/{pms_property_id}/special-offers/{offer_id}",
        json=update_payload,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    updated = data["data"]
    assert updated["title"] == "Early Bird 10% Updated"
    assert updated["discount_percentage"] == 12.0


@pytest.mark.asyncio
async def test_update_offer_invalid_dates(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    offer_id = pms_token_store["offer_id"]
    bad_payload = {
        "title": "Still Bad",
        "discount_percentage": 10.0,
        "start_date": _future_date(10),
        "end_date": _future_date(3),
        "is_active": False,
    }
    resp = await pms_client.patch(
        f"/properties/{pms_property_id}/special-offers/{offer_id}",
        json=bad_payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_update_offer_not_found(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    fake_id = "00000000-0000-0000-0000-000000000066"
    update_payload = {
        "title": "Ghost Offer",
        "discount_percentage": 5.0,
        "start_date": _future_date(5),
        "end_date": _future_date(10),
        "is_active": False,
    }
    resp = await pms_client.patch(
        f"/properties/{pms_property_id}/special-offers/{fake_id}",
        json=update_payload,
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# Delete
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_offer(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        "offers": [
            {
                **VALID_OFFER,
                "title": "To Delete",
            }
        ]
    }
    create_resp = await pms_client.post(
        f"/properties/{pms_property_id}/special-offers/",
        json=payload,
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    offer_id = create_resp.json()["data"][0]["id"]

    resp = await pms_client.delete(
        f"/properties/{pms_property_id}/special-offers/{offer_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_delete_offer_not_found(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    fake_id = "00000000-0000-0000-0000-000000000077"
    resp = await pms_client.delete(
        f"/properties/{pms_property_id}/special-offers/{fake_id}",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text
