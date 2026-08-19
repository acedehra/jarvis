import logging
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from psycopg.rows import dict_row
from app.core.database import get_db_pool

from zoneinfo import ZoneInfo
from app.core.config import settings

logger = logging.getLogger("tracker")

ALLOWED_CALCULATIONS = {"sum", "avg", "count", "min", "max"}


def _get_user_tz() -> Union[ZoneInfo, timezone]:
    try:
        return ZoneInfo(settings.USER_TIMEZONE)
    except Exception:
        return timezone.utc


def _parse_datetime(dt_val: Optional[Union[str, datetime]]) -> Optional[datetime]:
    """
    Parses datetime string or datetime object into a timezone-aware UTC datetime.
    If naive, attaches user's configured timezone before converting to UTC.
    """
    if dt_val is None:
        return None
    user_tz = _get_user_tz()
    
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=user_tz)
        return dt_val.astimezone(timezone.utc)
        
    if isinstance(dt_val, str):
        cleaned = dt_val.strip()
        if not cleaned:
            return None
        # Handle trailing Z
        if cleaned.endswith("Z") or cleaned.endswith("z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(cleaned)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=user_tz)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            try:
                # Try date-only format YYYY-MM-DD
                parsed = datetime.strptime(cleaned, "%Y-%m-%d")
                parsed = parsed.replace(tzinfo=user_tz)
                return parsed.astimezone(timezone.utc)
            except ValueError:
                logger.warning(f"Could not parse datetime string: '{dt_val}'")
                return None
    return None


def _to_user_tz_iso(dt_val: Optional[datetime]) -> Optional[str]:
    """
    Converts a datetime (from database/TIMESTAMPTZ) to an ISO string in user's configured timezone.
    """
    if not dt_val:
        return None
    if isinstance(dt_val, datetime):
        user_tz = _get_user_tz()
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=timezone.utc)
        return dt_val.astimezone(user_tz).isoformat()
    return str(dt_val)


async def create_or_update_record(
    collection: str,
    title: str,
    data: Optional[Dict[str, Any]] = None,
    event_date: Optional[Union[str, datetime]] = None,
    user_id: str = "default_user",
    record_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new tracking record or updates an existing record.
    """
    pool = get_db_pool()
    data = data or {}
    parsed_date = _parse_datetime(event_date)
    json_data = json.dumps(data)

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            if record_id:
                # Update existing record
                await cur.execute(
                    """
                    UPDATE tracker_items
                    SET collection = %s,
                        title = %s,
                        data = %s::jsonb,
                        event_date = %s,
                        updated_at = NOW()
                    WHERE id = %s AND user_id = %s
                    RETURNING id, user_id, collection, title, data, event_date, created_at, updated_at;
                    """,
                    (collection.lower().strip(), title.strip(), json_data, parsed_date, record_id, user_id),
                )
                row = await cur.fetchone()
                if not row:
                    raise ValueError(f"Record with id '{record_id}' not found for user '{user_id}'.")
                await conn.commit()
                return _format_row(row)
            else:
                # Insert new record
                await cur.execute(
                    """
                    INSERT INTO tracker_items (user_id, collection, title, data, event_date)
                    VALUES (%s, %s, %s, %s::jsonb, %s)
                    RETURNING id, user_id, collection, title, data, event_date, created_at, updated_at;
                    """,
                    (user_id, collection.lower().strip(), title.strip(), json_data, parsed_date),
                )
                row = await cur.fetchone()
                await conn.commit()
                return _format_row(row)


async def query_records(
    user_id: str = "default_user",
    collection: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    date_from: Optional[Union[str, datetime]] = None,
    date_to: Optional[Union[str, datetime]] = None,
    search_query: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Queries tracking records matching collection, JSON filters, date range, or text search.
    """
    pool = get_db_pool()
    conditions = ["user_id = %s"]
    params: List[Any] = [user_id]

    if collection:
        conditions.append("collection = %s")
        params.append(collection.lower().strip())

    if date_from:
        parsed_from = _parse_datetime(date_from)
        if parsed_from:
            conditions.append("COALESCE(event_date, created_at) >= %s")
            params.append(parsed_from)

    if date_to:
        parsed_to = _parse_datetime(date_to)
        if parsed_to:
            conditions.append("COALESCE(event_date, created_at) <= %s")
            params.append(parsed_to)

    if search_query:
        conditions.append("(title ILIKE %s OR data::text ILIKE %s)")
        search_pattern = f"%{search_query.strip()}%"
        params.extend([search_pattern, search_pattern])

    if filters:
        # JSON containment query
        conditions.append("data @> %s::jsonb")
        params.append(json.dumps(filters))

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT id, user_id, collection, title, data, event_date, created_at, updated_at
        FROM tracker_items
        WHERE {where_clause}
        ORDER BY COALESCE(event_date, created_at) DESC
        LIMIT %s OFFSET %s;
    """
    params.extend([limit, offset])

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [_format_row(r) for r in rows]


async def aggregate_records(
    user_id: str = "default_user",
    collection: str = "expense",
    calculation: str = "sum",
    field: Optional[str] = "amount",
    group_by: Optional[str] = None,
    date_from: Optional[Union[str, datetime]] = None,
    date_to: Optional[Union[str, datetime]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes native SQL calculations (SUM, AVG, COUNT, MIN, MAX) over JSON data fields.
    Guarantees deterministic math precision without relying on LLM token arithmetic.
    """
    calc_op = calculation.lower().strip()
    if calc_op not in ALLOWED_CALCULATIONS:
        raise ValueError(f"Invalid calculation '{calculation}'. Must be one of {ALLOWED_CALCULATIONS}")

    pool = get_db_pool()
    conditions = ["user_id = %s", "collection = %s"]
    params: List[Any] = [user_id, collection.lower().strip()]

    if date_from:
        parsed_from = _parse_datetime(date_from)
        if parsed_from:
            conditions.append("COALESCE(event_date, created_at) >= %s")
            params.append(parsed_from)

    if date_to:
        parsed_to = _parse_datetime(date_to)
        if parsed_to:
            conditions.append("COALESCE(event_date, created_at) <= %s")
            params.append(parsed_to)

    if filters:
        conditions.append("data @> %s::jsonb")
        params.append(json.dumps(filters))

    where_clause = " AND ".join(conditions)

    # Build SQL aggregate expression
    if calc_op == "count" and not field:
        agg_expr = "COUNT(*)"
    else:
        if not field:
            field = "amount"
        # Sanitize field name: only alphanumeric and underscores
        clean_field = "".join(c for c in field if c.isalnum() or c == "_")
        agg_expr = f"{calc_op.upper()}(COALESCE((data->>'{clean_field}')::numeric, 0))"

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            # 1. Total / primary aggregation
            total_sql = f"""
                SELECT 
                    {agg_expr} AS result,
                    COUNT(*) AS count
                FROM tracker_items
                WHERE {where_clause};
            """
            await cur.execute(total_sql, params)
            main_res = await cur.fetchone()
            result_val = float(main_res["result"]) if main_res and main_res["result"] is not None else 0.0
            count_val = int(main_res["count"]) if main_res and main_res["count"] is not None else 0

            response: Dict[str, Any] = {
                "collection": collection,
                "calculation": calc_op,
                "field": field if calc_op != "count" else None,
                "result": round(result_val, 2) if calc_op in {"sum", "avg", "min", "max"} else count_val,
                "record_count": count_val,
            }

            # 2. Group by breakdown (if requested)
            if group_by:
                clean_group = "".join(c for c in group_by if c.isalnum() or c == "_")
                group_sql = f"""
                    SELECT 
                        COALESCE(data->>'{clean_group}', 'Uncategorized') AS group_key,
                        {agg_expr} AS group_result,
                        COUNT(*) AS group_count
                    FROM tracker_items
                    WHERE {where_clause}
                    GROUP BY group_key
                    ORDER BY group_result DESC;
                """
                await cur.execute(group_sql, params)
                group_rows = await cur.fetchall()
                breakdown = {}
                for row in group_rows:
                    val = float(row["group_result"]) if row["group_result"] is not None else 0.0
                    breakdown[row["group_key"]] = {
                        "value": round(val, 2),
                        "count": row["group_count"],
                    }
                response["group_by"] = clean_group
                response["breakdown"] = breakdown

            return response


async def update_record_status(
    record_id: str,
    user_id: str = "default_user",
    status: Optional[str] = None,
    updates: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Updates status and/or arbitrary fields within record data.
    """
    pool = get_db_pool()
    merged_updates = dict(updates or {})
    if status is not None:
        merged_updates["status"] = status

    json_updates = json.dumps(merged_updates)

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                UPDATE tracker_items
                SET data = data || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s AND user_id = %s
                RETURNING id, user_id, collection, title, data, event_date, created_at, updated_at;
                """,
                (json_updates, record_id, user_id),
            )
            row = await cur.fetchone()
            await conn.commit()
            return _format_row(row) if row else None


async def delete_record(record_id: str, user_id: str = "default_user") -> bool:
    """
    Permanently deletes a tracking record.
    """
    pool = get_db_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "DELETE FROM tracker_items WHERE id = %s AND user_id = %s;",
                (record_id, user_id),
            )
            deleted = cur.rowcount > 0
            await conn.commit()
            return deleted


async def get_due_reminders(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetches all pending reminders where event_date is past or due now.
    """
    pool = get_db_pool()
    conditions = [
        "collection = 'reminder'",
        "event_date <= NOW()",
        "(data->>'status' IS NULL OR data->>'status' = 'scheduled' OR data->>'status' = 'pending')",
    ]
    params: List[Any] = []
    if user_id:
        conditions.append("user_id = %s")
        params.append(user_id)

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT id, user_id, collection, title, data, event_date, created_at, updated_at
        FROM tracker_items
        WHERE {where_clause}
        ORDER BY event_date ASC
        LIMIT 20;
    """
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
            return [_format_row(r) for r in rows]


async def mark_reminder_dispatched(record_id: str) -> bool:
    """
    Marks a reminder as sent after dispatching to Telegram.
    """
    pool = get_db_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                UPDATE tracker_items
                SET data = jsonb_set(
                    jsonb_set(data, '{status}', '"sent"'),
                    '{dispatched_at}',
                    to_jsonb(NOW()::text)
                ),
                updated_at = NOW()
                WHERE id = %s;
                """,
                (record_id,),
            )
            success = cur.rowcount > 0
            await conn.commit()
            return success


async def get_collections_summary(user_id: str = "default_user") -> List[Dict[str, Any]]:
    """
    Retrieves summary counts and recent timestamps for all collections.
    """
    pool = get_db_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT 
                    collection,
                    COUNT(*) AS count,
                    MAX(created_at) AS latest_created_at
                FROM tracker_items
                WHERE user_id = %s
                GROUP BY collection
                ORDER BY count DESC;
                """,
                (user_id,),
            )
            rows = await cur.fetchall()
            return [
                {
                    "collection": r["collection"],
                    "count": r["count"],
                    "latest_created_at": _to_user_tz_iso(r["latest_created_at"]),
                }
                for r in rows
            ]


async def get_gas_analytics(user_id: str = "default_user") -> Dict[str, Any]:
    """
    Computes specialized gas tracking metrics:
    - Total fuel cost
    - Total gallons/liters pumped
    - Average price per gallon
    - Fill-up count
    - Latest odometer reading
    - Average MPG (miles per gallon) based on consecutive odometer entries
    - Station breakdown
    """
    pool = get_db_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, user_id, collection, title, data, event_date, created_at, updated_at
                FROM tracker_items
                WHERE user_id = %s AND collection = 'gas'
                ORDER BY COALESCE(event_date, created_at) ASC;
                """,
                (user_id,),
            )
            rows = await cur.fetchall()

    if not rows:
        return {
            "total_spent": 0.0,
            "total_gallons": 0.0,
            "avg_price_per_gallon": 0.0,
            "fill_count": 0,
            "latest_odometer": None,
            "avg_mpg": None,
            "station_breakdown": {},
        }

    total_spent = 0.0
    total_gallons = 0.0
    stations: Dict[str, Dict[str, Any]] = {}
    latest_odometer: Optional[float] = None

    # MPG calculation across consecutive fill-ups
    mpg_readings: List[float] = []
    prev_odometer: Optional[float] = None

    for r in rows:
        d = r["data"] if isinstance(r["data"], dict) else json.loads(r["data"] or "{}")

        # Spent
        amt = float(d.get("amount", 0.0) or 0.0)
        total_spent += amt

        # Gallons
        gal = float(d.get("gallons", 0.0) or 0.0)
        total_gallons += gal

        # Odometer
        odo = d.get("odometer")
        if odo is not None:
            try:
                odo_val = float(odo)
                latest_odometer = odo_val
                if prev_odometer is not None and odo_val > prev_odometer and gal > 0:
                    mpg_readings.append((odo_val - prev_odometer) / gal)
                prev_odometer = odo_val
            except (ValueError, TypeError):
                pass

        # Station
        station = str(d.get("station") or "Other").strip()
        if station not in stations:
            stations[station] = {"spent": 0.0, "count": 0, "gallons": 0.0}
        stations[station]["spent"] = round(stations[station]["spent"] + amt, 2)
        stations[station]["count"] += 1
        stations[station]["gallons"] = round(stations[station]["gallons"] + gal, 2)

    avg_price = (total_spent / total_gallons) if total_gallons > 0 else 0.0
    avg_mpg = (sum(mpg_readings) / len(mpg_readings)) if mpg_readings else None

    return {
        "total_spent": round(total_spent, 2),
        "total_gallons": round(total_gallons, 2),
        "avg_price_per_gallon": round(avg_price, 2),
        "fill_count": len(rows),
        "latest_odometer": latest_odometer,
        "avg_mpg": round(avg_mpg, 1) if avg_mpg is not None else None,
        "station_breakdown": stations,
    }


def _format_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": str(row["id"]) if isinstance(row["id"], UUID) else str(row["id"]),
        "user_id": row["user_id"],
        "collection": row["collection"],
        "title": row["title"],
        "data": row["data"] if isinstance(row["data"], dict) else json.loads(row["data"] or "{}"),
        "event_date": _to_user_tz_iso(row.get("event_date")),
        "created_at": _to_user_tz_iso(row.get("created_at")),
        "updated_at": _to_user_tz_iso(row.get("updated_at")),
    }


