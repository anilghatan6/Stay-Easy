"""
Tests for /properties/{property_id}/discount-codes/* endpoints.

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


VALID_DISCOUNT_CODE = {
    "code": "SAVE10",
    "type": "PERCENTAGE",
    "discount_value": 10.0,
    "min_amount": 50.0,
    "max_uses": 100,
    "valid_from": _future_date(1),
    "valid_to": _future_date(30),
}


# ──────────────────────────────────────────────────────────────────────────────
# Unauthenticated — all endpoints without token → 401/403
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_discount_code_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/discount-codes/",
        json=VALID_DISCOUNT_CODE,
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_all_discount_codes_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.get(
        "/properties/00000000-0000-0000-0000-000000000000/discount-codes/",
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_discount_code_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.get(
        "/properties/00000000-0000-0000-0000-000000000000/discount-codes/00000000-0000-0000-0000-000000000000",
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_update_discount_code_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.patch(
        "/properties/00000000-0000-0000-0000-000000000000/discount-codes/00000000-0000-0000-0000-000000000000",
        json={"discount_value": 15.0},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_delete_discount_code_unauthenticated(pms_client: AsyncClient):
    resp = await pms_client.delete(
        "/properties/00000000-0000-0000-0000-000000000000/discount-codes/00000000-0000-0000-0000-000000000000",
    )
    assert resp.status_code in (401, 403), resp.text


# ──────────────────────────────────────────────────────────────────────────────
# Validation — bad payloads rejected
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_discount_code_empty_body(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/discount-codes/",
        json={},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_discount_code_short_code(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        **VALID_DISCOUNT_CODE,
        "code": "A",
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/discount-codes/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_discount_code_zero_discount_value(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        **VALID_DISCOUNT_CODE,
        "code": "ZERO",
        "discount_value": 0,
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/discount-codes/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_discount_code_zero_max_uses(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        **VALID_DISCOUNT_CODE,
        "code": "USES0",
        "max_uses": 0,
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/discount-codes/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_discount_code_valid_to_before_valid_from(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        **VALID_DISCOUNT_CODE,
        "code": "DATES",
        "valid_from": _future_date(10),
        "valid_to": _future_date(3),
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/discount-codes/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_discount_code_percentage_over_100(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        **VALID_DISCOUNT_CODE,
        "code": "PCT100",
        "type": "PERCENTAGE",
        "discount_value": 150.0,
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/discount-codes/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_discount_code_fixed_over_min_amount(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        **VALID_DISCOUNT_CODE,
        "code": "FIXED",
        "type": "FIXED",
        "discount_value": 100.0,
        "min_amount": 50.0,
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/discount-codes/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


# ──────────────────────────────────────────────────────────────────────────────
# Create success
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_discount_code_success(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/discount-codes/",
        json=VALID_DISCOUNT_CODE,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["success"] is True
    code = data["data"]
    for field in (
        "id", "property_id", "code", "type", "discount_value",
        "min_amount", "max_uses", "valid_from", "valid_to",
        "used_count", "created_at", "updated_at",
    ):
        assert field in code, f"Missing field: {field}"
    assert code["property_id"] == pms_property_id
    assert code["code"] == "SAVE10"
    assert code["type"] == "PERCENTAGE"
    assert code["used_count"] == 0

    pms_token_store["discount_id"] = code["id"]


# ──────────────────────────────────────────────────────────────────────────────
# Duplicate
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_discount_code_duplicate_code(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        **VALID_DISCOUNT_CODE,
        "discount_value": 20.0,
    }
    resp = await pms_client.post(
        f"/properties/{pms_property_id}/discount-codes/",
        json=payload,
        headers=headers,
    )
    assert resp.status_code in (400, 409), resp.text


# ──────────────────────────────────────────────────────────────────────────────
# Read
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_all_discount_codes(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/discount-codes/",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 1


@pytest.mark.asyncio
async def test_get_discount_code_by_id(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    discount_id = pms_token_store["discount_id"]
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/discount-codes/{discount_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    code = data["data"]
    assert code["id"] == discount_id
    assert code["code"] == "SAVE10"


@pytest.mark.asyncio
async def test_get_discount_code_not_found(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    fake_id = "00000000-0000-0000-0000-000000000055"
    resp = await pms_client.get(
        f"/properties/{pms_property_id}/discount-codes/{fake_id}",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


# ──────────────────────────────────────────────────────────────────────────────
# Update
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_discount_code_success(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    discount_id = pms_token_store["discount_id"]
    update_payload = {
        "discount_value": 15.0,
    }
    resp = await pms_client.patch(
        f"/properties/{pms_property_id}/discount-codes/{discount_id}",
        json=update_payload,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    updated = data["data"]
    assert updated["discount_value"] == 15.0


@pytest.mark.asyncio
async def test_update_discount_code_not_found(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    fake_id = "00000000-0000-0000-0000-000000000066"
    update_payload = {"discount_value": 25.0}
    resp = await pms_client.patch(
        f"/properties/{pms_property_id}/discount-codes/{fake_id}",
        json=update_payload,
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_update_discount_code_duplicate_code(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    other_payload = {
        **VALID_DISCOUNT_CODE,
        "code": "WELCOME",
    }
    create_resp = await pms_client.post(
        f"/properties/{pms_property_id}/discount-codes/",
        json=other_payload,
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    discount_id = pms_token_store["discount_id"]
    resp = await pms_client.patch(
        f"/properties/{pms_property_id}/discount-codes/{discount_id}",
        json={"code": "WELCOME"},
        headers=headers,
    )
    assert resp.status_code in (400, 409), resp.text


@pytest.mark.asyncio
async def test_update_discount_code_invalid_dates(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    discount_id = pms_token_store["discount_id"]
    bad_payload = {
        "valid_from": _future_date(10),
        "valid_to": _future_date(3),
    }
    resp = await pms_client.patch(
        f"/properties/{pms_property_id}/discount-codes/{discount_id}",
        json=bad_payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


# ──────────────────────────────────────────────────────────────────────────────
# Delete
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_discount_code(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    payload = {
        **VALID_DISCOUNT_CODE,
        "code": "TODEL",
    }
    create_resp = await pms_client.post(
        f"/properties/{pms_property_id}/discount-codes/",
        json=payload,
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    discount_id = create_resp.json()["data"]["id"]

    resp = await pms_client.delete(
        f"/properties/{pms_property_id}/discount-codes/{discount_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_delete_discount_code_not_found(
    pms_client: AsyncClient, pms_token_store: dict, pms_property_id: str
):
    headers = auth_headers(pms_token_store["access_token"])
    fake_id = "00000000-0000-0000-0000-000000000077"
    resp = await pms_client.delete(
        f"/properties/{pms_property_id}/discount-codes/{fake_id}",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text
