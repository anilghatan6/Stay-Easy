"""
Tests for /pms/{property_id}/special-offers/* endpoints.

Depends on `pms_client` + `pms_token_store` (from pms/conftest.py),
which already holds an access_token and property_id.
"""
from datetime import date, timedelta
import pytest
from httpx import AsyncClient


# ─── helpers ────────────────────────────────────────────────────────────────

def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _future_date(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()

@pytest.fixture(autouse=True)
async def setup_property(pms_property_id):
    pass

# ────────────────────────────────────────────────────────────────────────────
# POST /pms/{property_id}/special-offers — unauthenticated
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_offers_unauthenticated(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["property_id"]
    payload = {
        "offers": [
            {
                "title": "Early Bird 15%",
                "discount_percentage": 15.0,
                "start_date": _future_date(5),
                "end_date": _future_date(15),
                "is_active": True,
                "is_custom": False,
            }
        ]
    }
    resp = await pms_client.post(f"/pms/{prop_id}/special-offers", json=payload)
    assert resp.status_code in (401, 403), resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/{property_id}/special-offers — success (bulk)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_special_offers(pms_client: AsyncClient, pms_token_store: dict):
    prop_id = pms_token_store["property_id"]
    payload = {
        "offers": [
            {
                "title": "Early Bird 10%",
                "description": "Book 10 days in advance.",
                "discount_percentage": 10.0,
                "start_date": _future_date(5),
                "end_date": _future_date(20),
                "is_active": True,
                "is_custom": False,
            },
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
        f"/pms/{prop_id}/special-offers",
        json=payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["success"] is True
    offers = data["data"]
    assert isinstance(offers, list)
    assert len(offers) == 2

    # Validate response shape
    for offer in offers:
        for field in (
            "id", "property_id", "title", "discount_percentage",
            "start_date", "end_date", "is_active", "is_custom",
            "created_at", "updated_at",
        ):
            assert field in offer, f"Missing field: {field}"
        assert offer["property_id"] == prop_id

    # Persist first offer id for update tests
    pms_token_store["offer_id"] = offers[0]["id"]


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/{property_id}/special-offers — past start_date → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_offer_past_start_date(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["property_id"]
    payload = {
        "offers": [
            {
                "title": "Past Deal",
                "discount_percentage": 20.0,
                "start_date": _future_date(-10),   # past date
                "end_date": _future_date(5),
                "is_active": False,
                "is_custom": False,
            }
        ]
    }
    resp = await pms_client.post(
        f"/pms/{prop_id}/special-offers",
        json=payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/{property_id}/special-offers — start >= end → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_offer_start_after_end(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["property_id"]
    payload = {
        "offers": [
            {
                "title": "Bad Chronology",
                "discount_percentage": 10.0,
                "start_date": _future_date(10),
                "end_date": _future_date(5),   # end BEFORE start
                "is_active": False,
                "is_custom": False,
            }
        ]
    }
    resp = await pms_client.post(
        f"/pms/{prop_id}/special-offers",
        json=payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/{property_id}/special-offers — duplicate titles → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_offer_duplicate_titles(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["property_id"]
    payload = {
        "offers": [
            {
                "title": "Same Title",
                "discount_percentage": 5.0,
                "start_date": _future_date(3),
                "end_date": _future_date(8),
                "is_active": False,
                "is_custom": False,
            },
            {
                "title": "same title",   # case-insensitive duplicate
                "discount_percentage": 10.0,
                "start_date": _future_date(3),
                "end_date": _future_date(8),
                "is_active": False,
                "is_custom": False,
            },
        ]
    }
    resp = await pms_client.post(
        f"/pms/{prop_id}/special-offers",
        json=payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# POST /pms/{property_id}/special-offers — discount > 100 → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_offer_invalid_discount(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["property_id"]
    payload = {
        "offers": [
            {
                "title": "Too Good To Be True",
                "discount_percentage": 150.0,   # invalid — max is 100
                "start_date": _future_date(3),
                "end_date": _future_date(8),
                "is_active": False,
                "is_custom": False,
            }
        ]
    }
    resp = await pms_client.post(
        f"/pms/{prop_id}/special-offers",
        json=payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# GET /pms/{property_id}/special-offers — list
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_special_offers(pms_client: AsyncClient, pms_token_store: dict):
    prop_id = pms_token_store["property_id"]
    resp = await pms_client.get(
        f"/pms/{prop_id}/special-offers",
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 2


# ────────────────────────────────────────────────────────────────────────────
# GET /pms/{property_id}/special-offers — unauthenticated
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_special_offers_unauthenticated(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["property_id"]
    resp = await pms_client.get(f"/pms/{prop_id}/special-offers")
    assert resp.status_code in (401, 403), resp.text


# ────────────────────────────────────────────────────────────────────────────
# PATCH /pms/{property_id}/special-offers/{offer_id} — success
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_special_offer(pms_client: AsyncClient, pms_token_store: dict):
    prop_id = pms_token_store["property_id"]
    offer_id = pms_token_store["offer_id"]
    update_payload = {
        "title": "Early Bird 10% Updated",
        "description": "Updated offer description.",
        "discount_percentage": 12.0,
        "start_date": _future_date(6),
        "end_date": _future_date(22),
        "is_active": True,
        "is_custom": False,
    }
    resp = await pms_client.patch(
        f"/pms/{prop_id}/special-offers/{offer_id}",
        json=update_payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    updated = data["data"]
    assert updated["title"] == "Early Bird 10% Updated"
    assert updated["discount_percentage"] == 12.0


# ────────────────────────────────────────────────────────────────────────────
# PATCH /pms/{property_id}/special-offers/{offer_id} — invalid payload → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_special_offer_invalid_dates(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["property_id"]
    offer_id = pms_token_store["offer_id"]
    bad_payload = {
        "title": "Still Bad",
        "discount_percentage": 10.0,
        "start_date": _future_date(10),
        "end_date": _future_date(3),   # end before start
        "is_active": False,
        "is_custom": False,
    }
    resp = await pms_client.patch(
        f"/pms/{prop_id}/special-offers/{offer_id}",
        json=bad_payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# PATCH /pms/{property_id}/special-offers/{offer_id} — unknown offer → 404
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_special_offer_not_found(
    pms_client: AsyncClient, pms_token_store: dict
):
    prop_id = pms_token_store["property_id"]
    fake_offer_id = "00000000-0000-0000-0000-000000000055"
    update_payload = {
        "title": "Ghost Offer",
        "discount_percentage": 5.0,
        "start_date": _future_date(5),
        "end_date": _future_date(10),
        "is_active": False,
        "is_custom": False,
    }
    resp = await pms_client.patch(
        f"/pms/{prop_id}/special-offers/{fake_offer_id}",
        json=update_payload,
        headers=auth_headers(pms_token_store["access_token"]),
    )
    assert resp.status_code == 404, resp.text
