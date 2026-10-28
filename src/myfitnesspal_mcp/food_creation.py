"""Create foods in MyFitnessPal via the undocumented API."""

import logging
from typing import Any

import httpx

from .mfp_client import get_client, is_auth_error

logger = logging.getLogger(__name__)


def create_food(
    client: Any = None,
    *,
    name: str,
    brand: str | None = None,
    serving_size: str | None = None,
    calories: float = 0.0,
    protein: float = 0.0,
    carbs: float = 0.0,
    fat: float = 0.0,
    fiber: float | None = None,
    sugar: float | None = None,
    sodium: float | None = None,
    verified: bool = False,
) -> dict[str, Any]:
    """Create a food in MyFitnessPal via the undocumented POST /api/foods.

    Args:
        client: Authenticated MyFitnessPal client (resolved lazily if omitted).
        name: Food name (required).
        brand: Brand name (optional).
        serving_size: Serving size description (e.g. "100g", "1 cup").
        calories: Calories per serving.
        protein: Protein grams per serving.
        carbs: Carbs grams per serving.
        fat: Fat grams per serving.
        fiber: Fiber grams per serving (optional).
        sugar: Sugar grams per serving (optional).
        sodium: Sodium milligrams per serving (optional).
        verified: Whether the food is verified (default False).

    Returns:
        Dict with the created food's details (food_id, weight_id, etc.).

    Raises:
        RuntimeError: If the API request fails or the food is not created.
    """
    client = client or get_client()
    url = "https://www.myfitnesspal.com/api/foods"

    payload = {
        "name": name,
        "brand": brand or "",
        "serving_size": serving_size or "100g",
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
        "fiber": fiber or 0.0,
        "sugar": sugar or 0.0,
        "sodium": sodium or 0.0,
        "verified": verified,
    }

    try:
        response = client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        if is_auth_error(exc):
            raise RuntimeError(
                "MyFitnessPal rejected the session. Refresh credentials and retry."
            ) from exc
        raise RuntimeError(f"Failed to create food: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to create food: {exc}") from exc

    if not data.get("food_id") or not data.get("weight_id"):
        raise RuntimeError("Food creation succeeded but returned no food_id/weight_id")

    return {
        "food_id": data["food_id"],
        "weight_id": data["weight_id"],
        "name": name,
        "brand": brand or "",
        "serving_size": serving_size or "100g",
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
    }
