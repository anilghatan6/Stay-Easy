"""
Tests for /properties/{property_id}/staffs/* endpoints.

Covers happy path, edge cases and failed/validation cases for:
  - create staff            (POST   /properties/{pid}/staffs)
  - list staff              (GET    /properties/{pid}/staffs)
  - get staff by id         (GET    /properties/{pid}/staffs/{sid})
  - update staff            (PATCH  /properties/{pid}/staffs/{sid})
  - delete staff            (DELETE /properties/{pid}/staffs/{sid})
"""
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

CLOUDINARY_BASE = "https://res.cloudinary.com/drahdqd63/image/upload/"

VALID_STAFF_PAYLOAD = {
    "full_name": "John Doe",
    "email": "john.doe@staff.com",
    "phone_number": "9801234567",
    "job_role": "FRONT_DESK",
    "monthly_salary": "50000.00",
    "joining_date": "2024-01-15",
    "status": "ACTIVE",
}


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_uuid() -> str:
    return str(uuid.uuid4())


# ────────────────────────────────────────────────────────────────────────────
# Unauthenticated — all endpoints without a token → 401/403
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_staff_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/staffs",
        json=VALID_STAFF_PAYLOAD,
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_list_staff_unauthenticated(async_client: AsyncClient):
    resp = await async_client.get(
        "/properties/00000000-0000-0000-0000-000000000000/staffs"
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_get_staff_unauthenticated(async_client: AsyncClient):
    resp = await async_client.get(
        "/properties/00000000-0000-0000-0000-000000000000/staffs/"
        "00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_update_staff_unauthenticated(async_client: AsyncClient):
    resp = await async_client.patch(
        "/properties/00000000-0000-0000-0000-000000000000/staffs/"
        "00000000-0000-0000-0000-000000000000",
        json={"full_name": "Hacked"},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_delete_staff_unauthenticated(async_client: AsyncClient):
    resp = await async_client.delete(
        "/properties/00000000-0000-0000-0000-000000000000/staffs/"
        "00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code in (401, 403), resp.text


# ────────────────────────────────────────────────────────────────────────────
# Validation errors → 422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_staff_validation_errors(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    payload = {
        "full_name": "",
        "email": "not-an-email",
        "phone_number": "abc123",
        "job_role": "NOT_A_ROLE",
        "monthly_salary": "0",
        "joining_date": "not-a-date",
        "status": "BOGUS",
    }
    resp = await staff_admin_client.post(
        f"/properties/{staff_token_store['property_id']}/staffs",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_staff_bad_salary(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    payload = {**VALID_STAFF_PAYLOAD, "monthly_salary": "-1.00"}
    resp = await staff_admin_client.post(
        f"/properties/{staff_token_store['property_id']}/staffs",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_staff_phone_with_spaces(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    payload = {**VALID_STAFF_PAYLOAD, "phone_number": "  "}
    resp = await staff_admin_client.post(
        f"/properties/{staff_token_store['property_id']}/staffs",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_create_staff_bad_photo_url(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    payload = {
        **VALID_STAFF_PAYLOAD,
        "photos": {"profile": "https://evil.example.com/not-cloudinary.jpg"},
    }
    resp = await staff_admin_client.post(
        f"/properties/{staff_token_store['property_id']}/staffs",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# Create staff — happy path + business failures
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_staff_success(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    resp = await staff_admin_client.post(
        f"/properties/{staff_token_store['property_id']}/staffs",
        json=VALID_STAFF_PAYLOAD,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["full_name"] == VALID_STAFF_PAYLOAD["full_name"]
    assert data["email"] == VALID_STAFF_PAYLOAD["email"]
    assert data["job_role"] == VALID_STAFF_PAYLOAD["job_role"]
    assert data["status"] == "ACTIVE"
    assert Decimal(str(data["monthly_salary"])) == Decimal("50000.00")
    assert uuid.UUID(data["id"])
    staff_token_store["staff_id"] = data["id"]


@pytest.mark.asyncio
async def test_create_staff_duplicate_email(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    resp = await staff_admin_client.post(
        f"/properties/{staff_token_store['property_id']}/staffs",
        json=VALID_STAFF_PAYLOAD,
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert "already exists" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_create_staff_property_not_found(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    payload = {**VALID_STAFF_PAYLOAD, "email": "other.doe@staff.com"}
    resp = await staff_admin_client.post(
        f"/properties/{_create_uuid()}/staffs",
        json=payload,
        headers=headers,
    )
    assert resp.status_code in (400, 404), resp.text


# ────────────────────────────────────────────────────────────────────────────
# List staff
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_staff_success(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    resp = await staff_admin_client.get(
        f"/properties/{staff_token_store['property_id']}/staffs",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1
    assert body["meta"]["total"] >= 1
    assert body["meta"]["has_more"] is False


@pytest.mark.asyncio
async def test_list_staff_pagination(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    resp = await staff_admin_client.get(
        f"/properties/{staff_token_store['property_id']}/staffs",
        params={"skip": 0, "limit": 1},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["data"]) <= 1
    assert body["meta"]["limit"] == 1
    assert body["meta"]["skip"] == 0


@pytest.mark.asyncio
async def test_list_staff_property_not_found(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    resp = await staff_admin_client.get(
        f"/properties/{_create_uuid()}/staffs",
        headers=headers,
    )
    assert resp.status_code in (400, 404), resp.text


# ────────────────────────────────────────────────────────────────────────────
# Get staff by id
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_staff_success(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    staff_id = staff_token_store["staff_id"]
    resp = await staff_admin_client.get(
        f"/properties/{staff_token_store['property_id']}/staffs/{staff_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["id"] == staff_id


@pytest.mark.asyncio
async def test_get_staff_not_found(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    resp = await staff_admin_client.get(
        f"/properties/{staff_token_store['property_id']}/staffs/{_create_uuid()}",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_get_staff_property_not_found(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    resp = await staff_admin_client.get(
        f"/properties/{_create_uuid()}/staffs/{staff_token_store['staff_id']}",
        headers=headers,
    )
    assert resp.status_code in (400, 404), resp.text


# ────────────────────────────────────────────────────────────────────────────
# Update staff
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_staff_success(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    staff_id = staff_token_store["staff_id"]
    resp = await staff_admin_client.patch(
        f"/properties/{staff_token_store['property_id']}/staffs/{staff_id}",
        json={
            "full_name": "Jane Doe",
            "job_role": "MANAGER",
            "monthly_salary": "60000.00",
            "status": "ON_LEAVE",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["full_name"] == "Jane Doe"
    assert body["data"]["job_role"] == "MANAGER"
    assert body["data"]["status"] == "ON_LEAVE"
    assert Decimal(str(body["data"]["monthly_salary"])) == Decimal("60000.00")


@pytest.mark.asyncio
async def test_update_staff_email_conflict(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])

    create_resp = await staff_admin_client.post(
        f"/properties/{staff_token_store['property_id']}/staffs",
        json={**VALID_STAFF_PAYLOAD, "email": "second.doe@staff.com"},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    second_id = create_resp.json()["data"]["id"]

    resp = await staff_admin_client.patch(
        f"/properties/{staff_token_store['property_id']}/staffs/{second_id}",
        json={"email": VALID_STAFF_PAYLOAD["email"]},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_update_staff_not_found(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    resp = await staff_admin_client.patch(
        f"/properties/{staff_token_store['property_id']}/staffs/{_create_uuid()}",
        json={"full_name": "Ghost"},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


# ────────────────────────────────────────────────────────────────────────────
# Delete staff
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_staff_success(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    resp = await staff_admin_client.post(
        f"/properties/{staff_token_store['property_id']}/staffs",
        json={**VALID_STAFF_PAYLOAD, "email": "delete.me@staff.com"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    staff_id = resp.json()["data"]["id"]

    resp = await staff_admin_client.delete(
        f"/properties/{staff_token_store['property_id']}/staffs/{staff_id}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == "Staff deleted successfully"


@pytest.mark.asyncio
async def test_delete_staff_not_found(
    staff_admin_client: AsyncClient, staff_token_store: dict
):
    headers = _auth_headers(staff_token_store["access_token"])
    resp = await staff_admin_client.delete(
        f"/properties/{staff_token_store['property_id']}/staffs/{_create_uuid()}",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text