import asyncio
import json

import httpx
import pytest

from myfitnesspal_mcp import food_creation, server

API_URL = "https://www.myfitnesspal.com/api/foods"

EXPECTED_PAYLOAD = {
    "name": "Test Bar",
    "brand": "Acme",
    "serving_size": "1 bar",
    "calories": 200.0,
    "protein": 20.0,
    "carbs": 22.0,
    "fat": 7.0,
    "fiber": 3.0,
    "sugar": 5.0,
    "sodium": 140.0,
    "verified": True,
}


def make_client(calls, status=200, payload=None):
    """An httpx client whose transport is mocked, so POST /api/foods never
    leaves the test process while raising real HTTP errors on failure."""

    def handler(request):
        calls.append(request)
        if payload is not None:
            return httpx.Response(status, json=payload)
        return httpx.Response(
            status, json={"food_id": "food-1", "weight_id": "weight-1"}
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_create_food_posts_payload_and_returns_ids_and_macros():
    calls = []
    result = food_creation.create_food(
        make_client(calls),
        name="Test Bar",
        brand="Acme",
        serving_size="1 bar",
        calories=200,
        protein=20,
        carbs=22,
        fat=7,
        fiber=3,
        sugar=5,
        sodium=140,
        verified=True,
    )

    assert len(calls) == 1
    assert calls[0].method == "POST"
    assert str(calls[0].url) == API_URL
    assert json.loads(calls[0].content) == EXPECTED_PAYLOAD
    assert result == {
        "food_id": "food-1",
        "weight_id": "weight-1",
        "name": "Test Bar",
        "brand": "Acme",
        "serving_size": "1 bar",
        "calories": 200.0,
        "protein": 20.0,
        "carbs": 22.0,
        "fat": 7.0,
    }


def test_create_food_fills_optional_fields_with_defaults():
    calls = []
    result = food_creation.create_food(make_client(calls), name="Plain Oats")

    assert json.loads(calls[0].content) == {
        "name": "Plain Oats",
        "brand": "",
        "serving_size": "100g",
        "calories": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
        "fiber": 0.0,
        "sugar": 0.0,
        "sodium": 0.0,
        "verified": False,
    }
    assert result["food_id"] == "food-1"
    assert result["brand"] == ""
    assert result["serving_size"] == "100g"


def test_create_food_rejects_a_response_without_ids():
    calls = []
    with pytest.raises(RuntimeError, match="no food_id/weight_id"):
        food_creation.create_food(
            make_client(calls, payload={"food_id": "food-1"}), name="X"
        )


def test_create_food_reports_auth_failures_with_the_reconnect_hint():
    calls = []
    with pytest.raises(RuntimeError, match="Refresh credentials and retry"):
        food_creation.create_food(make_client(calls, status=401, payload={}), name="X")


def test_create_food_reports_other_api_failures():
    calls = []
    with pytest.raises(RuntimeError, match="Failed to create food"):
        food_creation.create_food(make_client(calls, status=500, payload={}), name="X")


@pytest.fixture
def mocked_api(monkeypatch):
    calls = []
    client = make_client(calls)
    monkeypatch.setattr(server.mfp_client, "get_client", lambda: client)
    monkeypatch.setattr(server.mfp_client, "persist_cached_session", lambda: None)
    return calls


def test_create_food_endpoint_returns_the_created_food(mocked_api):
    result = asyncio.run(
        server.fitness_create_food(
            name="Test Bar",
            brand="Acme",
            serving_size="1 bar",
            calories=200,
            protein=20,
            carbs=22,
            fat=7,
            fiber=3,
            sugar=5,
            sodium=140,
            verified=True,
        )
    )

    assert result["ok"] is True
    assert result["food_id"] == "food-1"
    assert result["weight_id"] == "weight-1"
    assert result["calories"] == 200.0
    assert result["protein"] == 20.0
    assert result["carbs"] == 22.0
    assert result["fat"] == 7.0
    assert json.loads(mocked_api[0].content) == EXPECTED_PAYLOAD


def test_create_food_tool_requires_a_name():
    tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
    schema = tools["fitness_create_food"].inputSchema
    assert schema["required"] == ["name"]
    assert {"brand", "serving_size", "calories", "protein", "carbs", "fat"} <= set(
        schema["properties"]
    )
    assert {"fiber", "sugar", "sodium", "verified"} <= set(schema["properties"])


def test_create_food_tool_is_registered_as_an_addition():
    tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
    tool = tools["fitness_create_food"]
    assert tool.title == "Create food"
    assert tool.annotations.readOnlyHint is False
    assert tool.annotations.destructiveHint is False
    assert tool.annotations.idempotentHint is False
    assert tool.annotations.openWorldHint is True
