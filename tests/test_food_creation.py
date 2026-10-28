"""fitness_create_food / custom_writes.create_food.

The request shape asserted here was verified live against a real account:
POST /api/services/foods with the item wrapper, the token from
/api/auth/csrf in X-CSRF-Token, and a 200 answered with the food it created.
"""

import asyncio
import json

import pytest
from conftest import FakeResponse

from myfitnesspal_mcp import custom_writes, server

FOODS_URL = "https://www.myfitnesspal.com/api/services/foods"
CSRF_URL = "https://www.myfitnesspal.com/api/auth/csrf"
CREATED = {"food_id": "9001", "weight_id": "9001", "description": "Oat bar"}


@pytest.fixture
def food_api(client):
    client.session.route(
        "GET", "api/auth/csrf", FakeResponse(json_data={"csrfToken": "csrf-1"})
    )
    client.session.route("POST", "api/services/foods", FakeResponse(json_data=CREATED))
    return client


def sent_item(client) -> dict:
    _, url, kwargs = [call for call in client.session.calls if call[0] == "POST"][-1]
    assert url == FOODS_URL
    assert kwargs["headers"]["X-CSRF-Token"] == "csrf-1"
    assert kwargs["headers"]["Accept"] == "application/json"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    return json.loads(kwargs["data"])["item"]


def test_create_food_posts_the_verified_payload(food_api):
    result = custom_writes.create_food(
        food_api,
        "Oat bar",
        calories=210,
        protein=9,
        carbs=30,
        fat=7,
        brand="Home",
        serving_size=55,
        serving_unit="g",
        fiber=4,
        sugar=5,
        sodium=140,
    )

    item = sent_item(food_api)
    assert item == {
        "description": "Oat bar",
        "public": False,
        "brand_name": "Home",
        "serving_sizes": [{"value": 55, "unit": "g", "nutrition_multiplier": 1}],
        "nutritional_contents": {
            "energy": {"unit": "calories", "value": 210},
            "protein": 9,
            "carbohydrates": 30,
            "fat": 7,
            "grams": 1,
            "fiber": 4,
            "sugar": 5,
            "sodium": 140,
        },
        "country_code": "PT",
        "user_id": "user-1",
    }
    assert result == {
        "food_id": "9001",
        "weight_id": "9001",
        "name": "Home - Oat bar",
        "brand": "Home",
        "serving": "55 g",
        "nutrition": {"calories": 210, "protein": 9, "carbs": 30, "fat": 7},
    }


def test_create_food_leaves_optional_nutrition_out_until_given(food_api):
    custom_writes.create_food(
        food_api, "Plain oats", calories=150, protein=5, carbs=27, fat=3
    )

    item = sent_item(food_api)
    assert set(item["nutritional_contents"]) == {
        "energy",
        "protein",
        "carbohydrates",
        "fat",
        "grams",
    }
    assert "brand_name" not in item
    assert item["serving_sizes"] == [
        {"value": 1, "unit": "serving", "nutrition_multiplier": 1}
    ]


def test_create_food_reads_the_item_wrapper_and_v2_ids(food_api):
    food_api.session.route(
        "POST",
        "api/services/foods",
        FakeResponse(json_data={"item": {"id": 11, "version": 12}}),
    )

    result = custom_writes.create_food(
        food_api, "Bar", calories=1, protein=0, carbs=0, fat=0
    )
    assert (result["food_id"], result["weight_id"]) == ("11", "12")


def test_create_food_needs_ids_to_be_loggable(food_api):
    food_api.session.route(
        "POST", "api/services/foods", FakeResponse(json_data={"food_id": "9001"})
    )
    with pytest.raises(RuntimeError, match="no food_id/weight_id"):
        custom_writes.create_food(
            food_api, "Bar", calories=1, protein=0, carbs=0, fat=0
        )


def test_create_food_reports_an_http_failure(food_api):
    food_api.session.route("POST", "api/services/foods", FakeResponse(status_code=500))
    with pytest.raises(RuntimeError, match="HTTP 500"):
        custom_writes.create_food(
            food_api, "Bar", calories=1, protein=0, carbs=0, fat=0
        )


def test_create_food_rejects_negative_or_empty_values(client):
    with pytest.raises(ValueError, match="description"):
        custom_writes.create_food(client, "  ", calories=1, protein=0, carbs=0, fat=0)
    with pytest.raises(ValueError, match="calories"):
        custom_writes.create_food(client, "Bar", calories=-5, protein=0, carbs=0, fat=0)
    with pytest.raises(ValueError, match="serving_size"):
        custom_writes.create_food(
            client, "Bar", calories=1, protein=0, carbs=0, fat=0, serving_size=0
        )
    assert not client.session.calls


def test_create_food_tool_requires_nutrition():
    tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
    schema = tools["fitness_create_food"].inputSchema
    assert schema["required"] == ["description", "calories", "protein", "carbs", "fat"]
    assert {
        "brand",
        "serving_size",
        "serving_unit",
        "fiber",
        "sugar",
        "sodium",
        "saturated_fat",
    } <= set(schema["properties"])


def test_create_food_tool_is_registered_as_an_addition():
    tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
    tool = tools["fitness_create_food"]
    assert tool.title == "Create food"
    assert tool.annotations.readOnlyHint is False
    assert tool.annotations.destructiveHint is False
    assert tool.annotations.idempotentHint is False
    assert tool.annotations.openWorldHint is True
