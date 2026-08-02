import uuid
from unittest.mock import AsyncMock
from httpx import AsyncClient

import pytest
from app.main import app
from app.modules.pms.dependencies import get_search_service
from app.modules.pms.services.search_service import SearchService

MOCK_RESULTS = [
    {
        "property_id": uuid.uuid4(),
        "name": "Test Hotel",
        "country": "New Zealand",
        "state": "Auckland",
        "city": "Auckland City",
        "address": "123 Ocean Drive",
        "type": "HOTEL",
        "cover_photo": "",
        "amenities": ["Free WiFi"],
        "description": "A test hotel",
        "currency": "USD",
        "total_price": 450.0,
        "nights": 3,
    }
]

MOCK_SERVICE_RESPONSE = {
    "data": {
        "adults": 2,
        "children": 1,
        "rooms": 1,
        "results": MOCK_RESULTS,
    },
    "meta": {
        "total": 1,
        "skip": 0,
        "limit": 10,
        "has_more": False,
    },
}

EMPTY_SERVICE_RESPONSE = {
    "data": {
        "adults": 2,
        "children": 1,
        "rooms": 1,
        "results": [],
    },
    "meta": {
        "total": 0,
        "skip": 0,
        "limit": 10,
        "has_more": False,
    },
}


def _mock_search_service(return_value: dict) -> AsyncMock:
    mock = AsyncMock(spec=SearchService)
    mock.search.return_value = return_value
    app.dependency_overrides[get_search_service] = lambda: mock
    return mock


@pytest.mark.asyncio
async def test_search_checkin_in_past(async_client: AsyncClient):
    params = {
        "destination": "Auckland",
        "check_in": "2020-01-01",
        "check_out": "2020-01-05",
        "adults": 2,
        "children": 0,
        "rooms": 1,
    }
    resp = await async_client.get("/search", params=params)
    assert resp.status_code == 400, resp.text
    assert "past" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_search_checkin_after_checkout(async_client: AsyncClient):
    params = {
        "destination": "Auckland",
        "check_in": "2030-01-05",
        "check_out": "2030-01-05",
        "adults": 2,
        "children": 0,
        "rooms": 1,
    }
    resp = await async_client.get("/search", params=params)
    assert resp.status_code == 400, resp.text
    assert "strictly before" in resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_search_destination_too_short(async_client: AsyncClient):
    params = {
        "destination": "A",
        "check_in": "2030-06-01",
        "check_out": "2030-06-05",
        "adults": 2,
        "children": 0,
        "rooms": 1,
    }
    resp = await async_client.get("/search", params=params)
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_search_success(async_client: AsyncClient):
    mock = _mock_search_service(MOCK_SERVICE_RESPONSE)

    params = {
        "destination": "Auckland",
        "check_in": "2030-06-01",
        "check_out": "2030-06-04",
        "adults": 2,
        "children": 1,
        "rooms": 1,
    }
    resp = await async_client.get("/search", params=params)

    app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True

    data = body["data"]
    assert data["adults"] == 2
    assert data["children"] == 1
    assert data["rooms"] == 1
    assert len(data["results"]) == 1

    result = data["results"][0]
    assert result["name"] == "Test Hotel"
    assert result["country"] == "New Zealand"
    assert float(result["total_price"]) == 450.0
    assert result["nights"] == 3

    meta = body["meta"]
    assert meta["total"] == 1
    assert meta["skip"] == 0
    assert meta["limit"] == 10
    assert meta["has_more"] is False


@pytest.mark.asyncio
async def test_search_no_results(async_client: AsyncClient):
    mock = _mock_search_service(EMPTY_SERVICE_RESPONSE)

    params = {
        "destination": "Nowhere",
        "check_in": "2030-07-01",
        "check_out": "2030-07-04",
        "adults": 2,
        "children": 0,
        "rooms": 1,
    }
    resp = await async_client.get("/search", params=params)

    app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]["results"]) == 0
    assert body["meta"]["total"] == 0
    assert body["meta"]["has_more"] is False


@pytest.mark.asyncio
async def test_search_pagination(async_client: AsyncClient):
    mock = _mock_search_service(MOCK_SERVICE_RESPONSE)

    params = {
        "destination": "Auckland",
        "check_in": "2030-08-01",
        "check_out": "2030-08-05",
        "adults": 2,
        "children": 0,
        "rooms": 1,
        "skip": 5,
        "limit": 20,
    }
    resp = await async_client.get("/search", params=params)

    app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    mock.search.assert_called_once()
    call_args = mock.search.call_args[0]
    assert call_args[6] == 5
    assert call_args[7] == 20
