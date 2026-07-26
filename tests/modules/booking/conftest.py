import pytest
import pytest_asyncio
from datetime import date, timedelta
from httpx import AsyncClient


@pytest.fixture(scope="session")
def booking_token_store() -> dict:
    return {}


async def _register_admin_and_create_tenant(client, store):
    email = "bk_admin@example.com"
    password = "SecurePassword123!"
    resp = await client.post(
        "/auth/users/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Booking Admin",
            "role": "admin",
            "phone": "9876543210",
        },
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        "/auth/users/verify-otp", json={"email": email, "otp": "123456"}
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post("/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    store["bk_access_token"] = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {store['bk_access_token']}"}
    resp = await client.post(
        "/tenants/",
        json={"name": "BK Test Hotel", "currency": "USD", "timezone": "UTC"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    store["bk_tenant_id"] = resp.json()["data"]["id"]


async def _register_guest_and_login(
    client, store, suffix="1", token_key="guest_access_token"
):
    email = f"booking.guest{suffix}@example.com"
    password = "SecurePass123!"
    resp = await client.post(
        "/auth/guests/register",
        json={
            "email": email,
            "password": password,
            "full_name": f"Booking Guest",
            "phone": f"987654321{suffix}",
        },
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        "/auth/guests/verify-otp", json={"email": email, "otp": "123456"}
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post("/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    store[token_key] = data["access_token"]
    store[f"{token_key}_refresh"] = data["refresh_token"]


@pytest_asyncio.fixture(scope="function")
async def bk_pms_client(async_client, booking_token_store):
    if "bk_access_token" not in booking_token_store:
        await _register_admin_and_create_tenant(async_client, booking_token_store)
    yield async_client


@pytest_asyncio.fixture(scope="function")
async def bk_property_id(bk_pms_client, booking_token_store):
    if "bk_property_id" not in booking_token_store:
        headers = {"Authorization": f"Bearer {booking_token_store['bk_access_token']}"}
        resp = await bk_pms_client.post(
            "/properties/general-information",
            json={
                "name": "BK Test Property",
                "type": "HOTEL",
                "description": "Booking test property",
                "phone_number": "1234567890",
                "email": "bk@test.property",
                "total_rooms": 10,
                "year_built": 2020,
                "number_of_floors": 3,
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        booking_token_store["bk_property_id"] = resp.json()["data"]["id"]
    return booking_token_store["bk_property_id"]


@pytest_asyncio.fixture(scope="function")
async def bk_room_setup(bk_pms_client, bk_property_id, booking_token_store):
    if "bk_room_id" not in booking_token_store:
        headers = {"Authorization": f"Bearer {booking_token_store['bk_access_token']}"}
        pid = booking_token_store["bk_property_id"]

        resp = await bk_pms_client.post(
            f"/properties/{pid}/rooms/room-type",
            json={"room_type_name": "Booking Suite"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        booking_token_store["bk_room_type_id"] = resp.json()["data"]["id"]

        resp = await bk_pms_client.post(
            f"/properties/{pid}/rooms/bed-type",
            json={"bed_name": "Queen"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        booking_token_store["bk_bed_type_id"] = resp.json()["data"]["id"]

        resp = await bk_pms_client.post(
            f"/properties/{pid}/rooms",
            json={
                "rooms": [
                    {
                        "room_name": "Room 101",
                        "floor_number": 1,
                        "max_adults": 2,
                        "max_children": 1,
                        "base_rate": "200.00",
                        "status": "AVAILABLE",
                        "cancellation_policy": "FLEXIBLE",
                        "room_type_id": booking_token_store["bk_room_type_id"],
                        "bed_type_id": booking_token_store["bk_bed_type_id"],
                        "photos": {"cover": None, "gallery": []},
                        "system_amenity_ids": [],
                        "custom_amenities": [],
                    },
                    {
                        "room_name": "Room 102",
                        "floor_number": 1,
                        "max_adults": 2,
                        "max_children": 0,
                        "base_rate": "250.00",
                        "status": "AVAILABLE",
                        "cancellation_policy": "FLEXIBLE",
                        "room_type_id": booking_token_store["bk_room_type_id"],
                        "bed_type_id": booking_token_store["bk_bed_type_id"],
                        "photos": {"cover": None, "gallery": []},
                        "system_amenity_ids": [],
                        "custom_amenities": [],
                    },
                ]
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        rooms = resp.json()["data"]["rooms"]
        room_map = {r["room_name"]: r["id"] for r in rooms}
        booking_token_store["bk_room_id"] = room_map["Room 101"]
        booking_token_store["bk_room_id_2"] = room_map["Room 102"]
    return booking_token_store


@pytest_asyncio.fixture(scope="function")
async def bk_discount_setup(bk_pms_client, bk_property_id, booking_token_store):
    if "bk_discount_id" not in booking_token_store:
        headers = {"Authorization": f"Bearer {booking_token_store['bk_access_token']}"}
        pid = booking_token_store["bk_property_id"]
        resp = await bk_pms_client.post(
            f"/properties/{pid}/discount-codes/",
            json={
                "code": "BOOKING10",
                "type": "PERCENTAGE",
                "discount_value": 10.0,
                "min_amount": 50.0,
                "max_uses": 100,
                "valid_from": future_date(-365),
                "valid_to": future_date(365),
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        booking_token_store["bk_discount_code"] = "BOOKING10"
        booking_token_store["bk_discount_id"] = resp.json()["data"]["id"]
    return booking_token_store


@pytest_asyncio.fixture(scope="function")
async def booking_guest_client(async_client, booking_token_store):
    if "guest_access_token" not in booking_token_store:
        await _register_guest_and_login(async_client, booking_token_store, "1")
    async_client.headers.update({
        "Authorization": f"Bearer {booking_token_store['guest_access_token']}"
    })
    yield async_client


@pytest_asyncio.fixture(scope="function")
async def booking_second_guest_client(async_client, booking_token_store):
    if "second_guest_access_token" not in booking_token_store:
        await _register_guest_and_login(
            async_client, booking_token_store, "2", "second_guest_access_token"
        )
    async_client.headers.update({
        "Authorization": f"Bearer {booking_token_store['second_guest_access_token']}"
    })
    yield async_client


def future_date(days_ahead: int) -> str:
    return (date.today() + timedelta(days=days_ahead)).isoformat()
