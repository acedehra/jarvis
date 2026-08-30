"""
Pantry / Grocery Inventory Service.

Provides deterministic management of a user's pantry ingredient inventory on top of the
generic `tracker_items` table (collection='pantry'). Each physical purchase/conversion is
stored as one record whose `data` blob carries `{name, quantity, unit, category, expiry}`.

This mirrors the Gas analytics precedent (see `tracker.get_gas_analytics`): the generic tracker
handles storage, and a thin, focused module owns the *domain semantics* (name normalization,
quantity math, dedup) so the LLM never has to reason about arithmetic or pluralization.
"""

import re
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.services.tracker import (
    create_or_update_record,
    query_records as db_query_records,
    update_record_status,
    delete_record,
    _parse_datetime,
)

logger = logging.getLogger("pantry")

PANTRY_COLLECTION = "pantry"
DEFAULT_USER = "default_user"

# Curated categories keep the data model tidy so grouping/suggestions stay deterministic.
VALID_CATEGORIES = {
    "produce",
    "dairy",
    "meat",
    "seafood",
    "bakery",
    "pantry",
    "spice",
    "frozen",
    "condiment",
    "other",
}


# --------------------------------------------------------------------------- normalization

def normalize_name(name: str) -> str:
    """
    Deterministically normalizes an ingredient name so that the same ingredient entered
    multiple ways ("tomatoes", "Tomato ", "tomato") dedupes into a single pantry item.

    Applied at write time (add) and read time (aggregation), keeping data consistent even for
    records previously created through the generic save_record tool.
    """
    if not name:
        return ""
    name = name.strip().lower()
    name = re.sub(r"\s+", " ", name)

    # Singularization heuristics for common English plurals (conservative & deterministic).
    if len(name) > 4 and name.endswith("ies"):
        name = name[:-3] + "y"  # berries -> berry, cherries -> cherry
    elif len(name) > 4 and (
        name.endswith("ches") or name.endswith("shes") or name.endswith("xes") or name.endswith("zes")
    ):
        name = name[:-2]  # dishes -> dish, boxes -> box, slices -> slice
    elif len(name) > 4 and name.endswith("oes"):
        name = name[:-2]  # tomatoes -> tomato, potatoes -> potato
    elif len(name) > 3 and name.endswith("s") and not name.endswith("ss"):
        name = name[:-1]  # apples -> apple, onions -> onion, eggs -> egg

    return name


def _sanitize_quantity(value: Any) -> float:
    """Parses quantity to a non-negative float, defaulting to 0.0 on empty/invalid input."""
    if value in (None, ""):
        return 0.0
    try:
        v = float(value)
        return v if v > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def _sanitize_category(category: Optional[str]) -> str:
    if not category:
        return "other"
    cat = category.strip().lower()
    return cat if cat in VALID_CATEGORIES else "other"


# --------------------------------------------------------------------------- helpers

async def _all_pantry_records() -> List[Dict[str, Any]]:
    """Fetches every pantry record for the default user."""
    return await db_query_records(
        user_id=DEFAULT_USER,
        collection=PANTRY_COLLECTION,
        limit=500,
    )


async def _find_records_by_normalized_name(name: str) -> List[Dict[str, Any]]:
    """Returns pantry records whose normalized title matches the given name."""
    target = normalize_name(name)
    if not target:
        return []
    records = await _all_pantry_records()
    return [r for r in records if normalize_name(r.get("title") or "") == target]


def _record_qty(record: Dict[str, Any]) -> float:
    return _sanitize_quantity((record.get("data") or {}).get("quantity"))


def _days_until_expiry(expiry: Any) -> Optional[int]:
    """
    Returns whole days from today until the given expiry value, or None if it can't be parsed.
    Negative means the item is already past its expiry. Uses the user's configured timezone date.
    """
    if not expiry:
        return None
    parsed = _parse_datetime(expiry)
    if parsed is None:
        return None
    today = datetime.now(_get_user_tz()).date()
    return (parsed.date() - today).days


def _get_user_tz():
    from zoneinfo import ZoneInfo
    from datetime import timezone as dt_timezone
    from app.core.config import settings
    try:
        return ZoneInfo(settings.USER_TIMEZONE)
    except Exception:
        return dt_timezone.utc


def _record_expiry(record: Dict[str, Any]) -> Optional[str]:
    return (record.get("data") or {}).get("expiry")



# --------------------------------------------------------------------------- public API

async def add_pantry_item(
    name: str,
    quantity: float = 1,
    unit: str = "items",
    category: Optional[str] = None,
    expiry: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Adds a quantity of an ingredient to the pantry.

    If an ingredient with the same normalized name already exists, the quantity is accumulated
    onto the existing record (and any provided unit/category/expiry become the new canonical
    values). Otherwise a new pantry record is created.
    """
    normalized = normalize_name(name)
    if not normalized:
        return {"ok": False, "reason": "invalid_name", "message": "Ingredient name is empty."}

    qty = _sanitize_quantity(quantity)
    unit_clean = (unit or "items").strip().lower().replace("pcs", "items").replace("piece", "item")
    if not unit_clean:
        unit_clean = "items"
    category_clean = _sanitize_category(category)

    existing = await _find_records_by_normalized_name(normalized)
    if existing:
        record = existing[0]
        data = dict(record.get("data") or {})
        new_qty = _record_qty(record) + qty
        data["name"] = normalized
        data["quantity"] = round(new_qty, 3)
        data["unit"] = unit_clean
        data["category"] = category_clean
        if expiry:
            data["expiry"] = expiry
        updated = await update_record_status(
            record_id=record["id"], user_id=DEFAULT_USER, updates=data
        )
        return {
            "ok": True,
            "action": "updated",
            "name": normalized,
            "quantity": data["quantity"],
            "unit": data["unit"],
            "category": data["category"],
            "record_id": record["id"],
            "message": f"Updated '{normalized}' in pantry (now {data['quantity']} {data['unit']}).",
        }

    data = {
        "name": normalized,
        "quantity": qty,
        "unit": unit_clean,
        "category": category_clean,
    }
    if expiry:
        data["expiry"] = expiry

    record = await create_or_update_record(
        collection=PANTRY_COLLECTION,
        title=normalized,
        data=data,
        event_date=None,
        user_id=DEFAULT_USER,
    )
    return {
        "ok": True,
        "action": "created",
        "name": normalized,
        "quantity": qty,
        "unit": unit_clean,
        "category": category_clean,
        "record_id": record["id"],
        "message": f"Added '{normalized}' ({qty} {unit_clean}) to pantry.",
    }


async def consume_from_pantry(name: str, quantity: float = 1) -> Dict[str, Any]:
    """
    Consumes a quantity of an ingredient (e.g. when cooking).

    Decrements across matching records. Records whose quantity reaches zero are deleted.
    Reports any shortfall if the requested quantity exceeds what's in stock.
    """
    requested = _sanitize_quantity(quantity)
    normalized = normalize_name(name)
    if not normalized:
        return {"ok": False, "message": "Ingredient name is empty."}

    matches = await _find_records_by_normalized_name(normalized)
    if not matches:
        return {
            "ok": False,
            "name": normalized,
            "message": f"'{normalized}' is not in the pantry.",
        }

    available = sum(_record_qty(r) for r in matches)
    if available <= 0:
        return {"ok": False, "name": normalized, "message": f"'{normalized}' is out of stock."}

    take = min(requested, available)
    remaining_to_consume = take
    for record in matches:
        if remaining_to_consume <= 0:
            break
        rec_qty = _record_qty(record)
        if rec_qty <= 0:
            continue
        subtract = min(rec_qty, remaining_to_consume)
        new_qty = round(rec_qty - subtract, 3)
        remaining_to_consume = round(remaining_to_consume - subtract, 3)
        if new_qty <= 0:
            await delete_record(record_id=record["id"], user_id=DEFAULT_USER)
        else:
            data = dict(record.get("data") or {})
            data["quantity"] = new_qty
            await update_record_status(record_id=record["id"], user_id=DEFAULT_USER, updates=data)

    shortfall = round(requested - take, 3)
    msg = f"Consumed {take} {matches[0].get('data', {}).get('unit', 'item')} of '{normalized}'."
    if shortfall > 0:
        msg += f" Only {available} were available; you're short {shortfall}."
    elif (available - take) <= 0:
        msg += " It is now out of stock."
    return {
        "ok": True,
        "name": normalized,
        "consumed": take,
        "remaining": round(max(available - take, 0.0), 3),
        "shortfall": shortfall,
        "message": msg,
    }


async def get_pantry_inventory(include_empty: bool = False) -> Dict[str, Any]:
    """
    Returns the entire pantry inventory, aggregated by normalized ingredient name.

    Quantities across duplicate records are summed and unit/category are reconciled, so the
    result is a clean, deterministic snapshot the LLM can reason over for meal planning.
    """
    records = await _all_pantry_records()
    aggregated: Dict[str, Dict[str, Any]] = {}
    total_items = 0

    for record in records:
        data = record.get("data") or {}
        raw_name = record.get("title") or data.get("name")
        normalized = normalize_name(str(raw_name))
        if not normalized:
            continue

        item = aggregated.setdefault(
            normalized,
            {
                "id": record["id"],
                "name": normalized,
                "quantity": 0.0,
                "unit": (data.get("unit") or "items"),
                "category": (data.get("category") or "other"),
                "expiry": data.get("expiry"),
                "sources": 1,
            },
        )
        item["quantity"] = round(item["quantity"] + _record_qty(record), 3)
        if data.get("unit"):
            item["unit"] = data["unit"]
        if data.get("category"):
            item["category"] = data["category"]
        if data.get("expiry") and (not item["expiry"] or str(data["expiry"]) > str(item["expiry"])):
            item["expiry"] = data["expiry"]
        item["sources"] += 1
        total_items += 1

    inventory = list(aggregated.values())
    if not include_empty:
        inventory = [i for i in inventory if i["quantity"] > 0]

    # Attach deterministic expiry horizon for every item so plan / alert logic can act on it.
    for item in inventory:
        item["days_to_expiry"] = _days_until_expiry(item.get("expiry"))

    # Sort: expiring-soonest first, then alphabetically.
    inventory.sort(
        key=lambda i: (
            0 if i.get("days_to_expiry") is not None else 1,   # items with a date first
            i.get("days_to_expiry") if i.get("days_to_expiry") is not None else 10**9,  # soonest first
            i["name"],
        )
    )

    return {
        "count": len(inventory),
        "distinct_sources": total_items,
        "items": inventory,
    }


async def get_expiring_items(
    within_days: int = 3,
    include_expired: bool = True,
    user_id: str = DEFAULT_USER,
) -> List[Dict[str, Any]]:
    """
    Returns pantry items that expire within `within_days` days from now.

    Items whose expiry date is unknown are excluded. When `include_expired` is True (default),
    items already past their expiry date are included at the front. Results are ordered by
    soonest-expiry first.

    Each result includes the normalized name, aggregated quantity/unit, expiry, days_to_expiry,
    and whether it has already been alerted to the user.
    """
    records = await _all_pantry_records()
    by_name: Dict[str, Dict[str, Any]] = {}

    for record in records:
        data = record.get("data") or {}
        expiry = data.get("expiry")
        if not expiry:
            continue
        days = _days_until_expiry(expiry)
        if days is None:
            continue
        # Include already-expired items only when requested; otherwise ignore stale records.
        if days < 0:
            if not include_expired:
                continue
        # Skip items that are still within their margin and won't expire in the window.
        elif days > within_days:
            continue


        raw_name = record.get("title") or data.get("name")
        normalized = normalize_name(str(raw_name))
        if not normalized:
            continue
        item = by_name.setdefault(
            normalized,
            {
                "item_id": record["id"],
                "id": record["id"],
                "name": normalized,
                "quantity": 0.0,
                "unit": (data.get("unit") or "items"),
                "expiry": expiry,
                "days_to_expiry": days,
                "alerted": bool(data.get("expiry_alerted")),
            },
        )
        item["quantity"] = round(item["quantity"] + _record_qty(record), 3)

    expiring = list(by_name.values())
    expiring.sort(
        key=lambda i: (i["days_to_expiry"] or 0, i["name"])
    )
    return expiring


async def mark_expiry_alerted(record_id: str, user_id: str = DEFAULT_USER) -> Optional[Dict[str, Any]]:
    """
    Marks a pantry record's expiry alert as dispatched so the worker does not re-alert.
    Returns the updated record (with data.expiry_alerted = True) or None if not found.
    """
    from datetime import datetime as _dt, timezone as _tz
    return await update_record_status(
        record_id=record_id,
        user_id=user_id,
        updates={"expiry_alerted": True, "expiry_alerted_at": _dt.now(_tz.utc).isoformat()},
    )


async def get_meal_plan(limit: int = 6) -> Dict[str, Any]:
    """
    Builds the "meal base": a deterministic snapshot of what's in the pantry plus the items
    expiring soonest. The LLM uses this to propose meals built from what you actually have,
    prioritized to use up near-expiring ingredients before they spoil.

    Returns structured data (not prose) so the model can reason over exact quantities.
    """
    inventory = await get_pantry_inventory(include_empty=False)
    items = inventory["items"]
    # Headline the soon-to-expire items (what the plan should use first).
    expiring = [
        {
            "name": i["name"],
            "quantity": i["quantity"],
            "unit": i["unit"],
            "expiry": i["expiry"],
            "days_to_expiry": i["days_to_expiry"],
        }
        for i in items
        if i.get("days_to_expiry") is not None and (i["days_to_expiry"] or 0) <= 3
    ]
    return {
        "count": inventory["count"],
        "available_stock": items,
        "expiring_soon": expiring,
        "meal_limit": limit,
    }