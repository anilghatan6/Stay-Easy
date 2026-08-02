"""
Tests for /properties/{property_id}/images/* endpoints.

Covers happy path, edge cases and failed cases for:
  - bulk property image upload    (POST /properties/{pid}/images)
  - bulk room image upload        (POST /properties/{pid}/rooms/images)
  - single property image upload  (POST /properties/{pid}/image)
  - single staff image upload     (POST /properties/{pid}/staffs/image)
  - single room image upload      (POST /properties/{pid}/rooms/image)

The image storage provider is Cloudinary, so ImageService methods are mocked.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.modules.pms.services.image_services import ImageService

PNG_BYTES = b"\x89PNG\r\n\x1a\n fake image bytes"


@pytest_asyncio.fixture(scope="function")
async def ensure_property(pms_client, pms_token_store):
    if "property_id" not in pms_token_store:
        headers = {"Authorization": f"Bearer {pms_token_store['access_token']}"}
        payload = {
            "name": "Image Test Hotel",
            "type": "HOTEL",
            "description": "Hotel for image endpoints.",
            "phone_number": "1234567890",
            "email": "img@hotel.com",
            "total_rooms": 10,
            "year_built": 2000,
            "number_of_floors": 3,
        }
        resp = await pms_client.post(
            "/properties/general-information", json=payload, headers=headers
        )
        assert resp.status_code == 201, resp.text
        pms_token_store["property_id"] = resp.json()["data"]["id"]
    return pms_token_store["property_id"]


def _files(*names: str) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        (f"files", (name, PNG_BYTES, "image/png"))
        for name in names
    ]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ────────────────────────────────────────────────────────────────────────────
# Unauthenticated — all endpoints without a token → 401/403
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_images_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/images",
        files=_files("a.png"),
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_upload_room_images_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/rooms/images",
        files=_files("a.png"),
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_upload_property_image_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/image",
        files={"image": ("a.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_upload_staff_image_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/staffs/image",
        files={"image": ("a.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.asyncio
async def test_upload_room_image_unauthenticated(async_client: AsyncClient):
    resp = await async_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/rooms/image",
        files={"image": ("a.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code in (401, 403), resp.text


# ────────────────────────────────────────────────────────────────────────────
# No-tenant admin → 400 (the router explicitly guards tenant_id is None)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_images_no_tenant(async_client: AsyncClient, mocker):
    token = await _register_no_tenant_admin(async_client)
    headers = _auth_headers(token)

    resp = await async_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/images",
        files=_files("a.png"),
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert "active tenant" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_upload_property_image_no_tenant(async_client: AsyncClient, mocker):
    token = await _register_no_tenant_admin(async_client)
    headers = _auth_headers(token)

    resp = await async_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/image",
        files={"image": ("a.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_upload_room_image_no_tenant(async_client: AsyncClient, mocker):
    token = await _register_no_tenant_admin(async_client)
    headers = _auth_headers(token)

    resp = await async_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/rooms/image",
        files={"image": ("a.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_upload_staff_image_no_tenant(async_client: AsyncClient, mocker):
    token = await _register_no_tenant_admin(async_client)
    headers = _auth_headers(token)

    resp = await async_client.post(
        "/properties/00000000-0000-0000-0000-000000000000/staffs/image",
        files={"image": ("a.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text


# ────────────────────────────────────────────────────────────────────────────
# Validation → 400/422
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_more_than_five_files(pms_client: AsyncClient, pms_token_store: dict, ensure_property: str):
    headers = _auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_token_store['property_id']}/images",
        files=_files("a.png", "b.png", "c.png", "d.png", "e.png", "f.png"),
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert "5 files" in resp.json()["error"]


@pytest.mark.asyncio
async def test_upload_room_images_more_than_five(
    pms_client: AsyncClient, pms_token_store: dict, ensure_property: str
):
    headers = _auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_token_store['property_id']}/rooms/images",
        files=_files("a.png", "b.png", "c.png", "d.png", "e.png", "f.png"),
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert "Bulk upload constraint" in resp.json()["error"]


@pytest.mark.asyncio
async def test_upload_non_image_file(pms_client: AsyncClient, pms_token_store: dict, ensure_property: str):
    headers = _auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_token_store['property_id']}/images",
        files=[("files", ("doc.txt", b"plain text", "text/plain"))],
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
    assert "invalid" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_upload_property_image_non_image(
    pms_client: AsyncClient, pms_token_store: dict, ensure_property: str
):
    headers = _auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_token_store['property_id']}/image",
        files={"image": ("doc.txt", b"plain text", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_upload_no_files(pms_client: AsyncClient, pms_token_store: dict, ensure_property: str):
    headers = _auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_token_store['property_id']}/images",
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


# ────────────────────────────────────────────────────────────────────────────
# Happy paths — ImageService mocked to avoid Cloudinary
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_images_success(pms_client: AsyncClient, pms_token_store: dict, ensure_property: str, mocker):
    url = f"https://res.cloudinary.com/demo/image/upload/v1/temp/{pms_token_store['tenant_id']}/properties/{pms_token_store['property_id']}/a.webp"
    mocker.patch.object(
        ImageService, "upload_property_images", return_value=[url]
    )
    headers = _auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_token_store['property_id']}/images",
        files=_files("a.png"),
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == [url]


@pytest.mark.asyncio
async def test_upload_images_multi_success(
    pms_client: AsyncClient, pms_token_store: dict, ensure_property: str, mocker
):
    urls = [f"https://res.cloudinary.com/demo/image/upload/v1/file{i}.webp" for i in range(3)]
    mock = mocker.patch.object(
        ImageService, "upload_property_images", return_value=urls
    )
    headers = _auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_token_store['property_id']}/images",
        files=_files("a.png", "b.png", "c.png"),
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"] == urls
    assert mock.await_count == 1
    folder = mock.await_args.kwargs["folder_name"]
    assert folder.startswith(f"temp/{pms_token_store['tenant_id']}")


@pytest.mark.asyncio
async def test_upload_room_images_success(
    pms_client: AsyncClient, pms_token_store: dict, ensure_property: str, mocker
):
    url = "https://res.cloudinary.com/demo/image/upload/v1/rooms/r.webp"
    mock = mocker.patch.object(
        ImageService, "upload_property_images", return_value=[url]
    )
    headers = _auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_token_store['property_id']}/rooms/images",
        files=_files("a.png"),
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"] == [url]
    folder = mock.await_args.kwargs["folder_name"]
    assert f"rooms" in folder


@pytest.mark.asyncio
async def test_upload_property_image_success(
    pms_client: AsyncClient, pms_token_store: dict, ensure_property: str, mocker
):
    url = "https://res.cloudinary.com/demo/image/upload/v1/prop.webp"
    mock = mocker.patch.object(
        ImageService, "_process_and_upload_single", return_value=url
    )
    headers = _auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_token_store['property_id']}/image",
        files={"image": ("a.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == url
    folder = mock.await_args.kwargs["folder_name"]
    assert f"temp/{pms_token_store['tenant_id']}/properties" in folder


@pytest.mark.asyncio
async def test_upload_staff_image_success(
    pms_client: AsyncClient, pms_token_store: dict, ensure_property: str, mocker
):
    url = "https://res.cloudinary.com/demo/image/upload/v1/staff.webp"
    mock = mocker.patch.object(
        ImageService, "_process_and_upload_single", return_value=url
    )
    headers = _auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_token_store['property_id']}/staffs/image",
        files={"image": ("a.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == url
    folder = mock.await_args.kwargs["folder_name"]
    assert "staffs" in folder


@pytest.mark.asyncio
async def test_upload_room_image_success(
    pms_client: AsyncClient, pms_token_store: dict, ensure_property: str, mocker
):
    url = "https://res.cloudinary.com/demo/image/upload/v1/room.webp"
    mock = mocker.patch.object(
        ImageService, "_process_and_upload_single", return_value=url
    )
    headers = _auth_headers(pms_token_store["access_token"])
    resp = await pms_client.post(
        f"/properties/{pms_token_store['property_id']}/rooms/image",
        files={"image": ("a.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == url
    folder = mock.await_args.kwargs["folder_name"]
    assert "rooms" in folder


# ────────────────────────────────────────────────────────────────────────────
# Helper: register an admin WITHOUT a tenant (tenant_id is None)
# ────────────────────────────────────────────────────────────────────────────

_admin_cache: dict = {}


async def _register_no_tenant_admin(client: AsyncClient) -> str:
    if _admin_cache.get("token"):
        return _admin_cache["token"]

    email = "img.nonadmin@example.com"
    password = "SecurePassword123!"
    resp = await client.post(
        "/auth/users/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Image No Tenant",
            "phone": "9876543210",
        },
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        "/auth/users/verify-otp", json={"email": email, "otp": "123456"}
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    _admin_cache["token"] = resp.json()["access_token"]
    return _admin_cache["token"]