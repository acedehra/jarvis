"""
Meal Planner Service.

Generates meal plans from the user's ACTUAL pantry inventory. This runs a stateless, structured
LLM call (mirroring `memory_reflection.extract_memories_async`) so the frontend Pantry page can
request a plan with one REST call — it deliberately does NOT go through the agent graph. The LLM
is asked to build meals only from confirmed stock (plus ubiquitous staples) and to call out missing
ingredients, so the plan is grounded in reality and actionable.
"""

import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.llm import get_llm_model
from app.services.pantry import get_pantry_inventory

logger = logging.getLogger("meal_planner")


# --------------------------------------------------------------------------- structured schema

class MissingIngredient(BaseModel):
    name: str = Field(..., description="Ingredient you don't have that the recipe needs.")
    quantity: Optional[str] = Field(None, description="Approx amount needed, e.g. '200g' or '2 cloves'.")
    required: bool = Field(True, description="True if essential; False if it's a nice-to-have you can skip or substitute.")


class MealSuggestion(BaseModel):
    name: str = Field(..., description="Short dish name, e.g. 'Chicken & Tomato Pasta'.")
    summary: str = Field(..., description="One sentence describing the dish.")
    uses_expiring: bool = Field(False, description="True if this meal deliberately uses up an expiring ingredient.")
    missing_ingredients: List[MissingIngredient] = Field(
        default_factory=list,
        description="Ingredients required but not in stock. Empty list = fully cookable with what you have.",
    )


class MealPlan(BaseModel):
    meals: List[MealSuggestion] = Field(..., description="Suggested meals, best first.")
    note: str = Field("", description="Short practical note (e.g. which expiring item to use first).")


# --------------------------------------------------------------------------- prompt

SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S., the user's precise and practical meal-planning assistant.\n"
    "Given the user's actual pantry inventory, propose realistic, varied meals.\n"
    "Rules:\n"
    "1. ONLY build dishes from ingredients confirmed in the inventory, plus ubiquitous staples "
    "(salt, pepper, cooking oil, water, basic spices) that everyone always has.\n"
    "2. PRIORITIZE using up items that are expiring soon or already expired (marked with days_to_expiry).\n"
    "3. Be honest: if a dish needs an ingredient not in stock, list it under missing_ingredients "
    "(set required=True only if it truly can't be substituted or skipped).\n"
    "4. Keep it to a handful of genuinely cookable meals rather than padding with fantasy dishes.\n"
    "5. meals should be ordered: things that use expiring ingredients first, then the rest.\n"
)

USER_TEMPLATE = (
    "Here is my current pantry inventory:\n"
    "{inventory}\n\n"
    "Suggest {requested} meal(s) I can cook from what I have."
)


# --------------------------------------------------------------------------- public API

async def generate_meal_plan(requested: int = 3) -> dict:
    """
    Builds a meal plan from the pantry inventory via a single structured LLM call.
    Falls back to a graceful, deterministic empty-plan on any failure (never crashes the page).
    """
    inventory = await get_pantry_inventory(include_empty=False)

    if inventory["count"] == 0:
        return _empty_plan("Your pantry is empty. Add ingredients first.")

    # Compact, LLM-friendly inventory dump (names, totals, unit, expiry horizon).
    lines = []
    for item in inventory["items"]:
        name = item["name"]
        qty = item["quantity"]
        unit = item["unit"]
        d = item.get("days_to_expiry")
        if d is not None and d < 0:
            marker = f" [EXPIRED {abs(d)}d ago]"
        elif d is not None and d <= 3:
            marker = f" [expires in {d}d]"
        elif d is not None:
            marker = f" [expires in {d}d]"
        else:
            marker = ""
        lines.append(f"- {qty} {unit} {name}{marker}")
    inventory_str = "\n".join(lines)

    try:
        llm = get_llm_model(provider="gemini", model_name=settings.DEFAULT_GEMINI_MODEL)
        structured_llm = llm.with_structured_output(MealPlan)

        from langchain_core.messages import SystemMessage, HumanMessage
        result: MealPlan = await structured_llm.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=USER_TEMPLATE.format(requested=requested, inventory=inventory_str)),
            ]
        )

        return {
            "ok": True,
            "generated": True,
            "requested": requested,
            "meals": [
                {
                    "name": m.name,
                    "summary": m.summary,
                    "uses_expiring": m.uses_expiring,
                    "missing_ingredients": [
                        {"name": mi.name, "quantity": mi.quantity, "required": mi.required}
                        for mi in m.missing_ingredients
                    ],
                }
                for m in result.meals
            ],
            "note": result.note,
        }
    except Exception as e:
        logger.error(f"Meal-plan LLM call failed: {e}", exc_info=True)
        return _empty_plan("Could not generate a meal plan right now. Please try again shortly.")


def _empty_plan(message: str) -> dict:
    return {
        "ok": True,
        "generated": False,
        "requested": 0,
        "meals": [],
        "note": message,
    }
