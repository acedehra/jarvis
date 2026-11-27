from datetime import datetime
from typing import Optional
from psycopg.rows import dict_row
from pydantic import BaseModel, Field
from app.core.database import get_db_pool


CREATE_MEALS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS meals (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    meal_type TEXT NOT NULL,
    prep_time_minutes INTEGER,
    ingredients TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


class MealCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Name of the meal")
    meal_type: str = Field(
        ...,
        min_length=1,
        description="Meal type (e.g. breakfast, lunch, dinner, snack)",
    )
    prep_time_minutes: Optional[int] = Field(
        default=None, ge=0, description="Preparation time in minutes"
    )
    ingredients: list[str] = Field(
        default_factory=list, description="List of ingredients needed for the meal"
    )


class Meal(BaseModel):
    id: int
    name: str
    meal_type: str
    prep_time_minutes: Optional[int] = None
    ingredients: list[str]
    created_at: datetime


async def init_meals_table() -> None:
    pool = get_db_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(CREATE_MEALS_TABLE_SQL)
            await conn.commit()


async def create_meal(data: MealCreate) -> dict:
    pool = get_db_pool()
    cleaned_name = data.name.strip()
    cleaned_type = data.meal_type.strip().lower()
    cleaned_ingredients = [i.strip() for i in data.ingredients if i and i.strip()]

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO meals (name, meal_type, prep_time_minutes, ingredients)
                VALUES (%s, %s, %s, %s)
                RETURNING id, name, meal_type, prep_time_minutes, ingredients, created_at
                """,
                (cleaned_name, cleaned_type, data.prep_time_minutes, cleaned_ingredients),
            )
            row = await cur.fetchone()
            await conn.commit()
            return dict(row)


async def list_meals(
    meal_type: Optional[str] = None,
    max_prep_time_minutes: Optional[int] = None,
    ingredient: Optional[str] = None,
) -> list[dict]:
    pool = get_db_pool()
    conditions: list[str] = []
    params: list = []

    if meal_type and meal_type.strip():
        conditions.append("LOWER(meal_type) = LOWER(%s)")
        params.append(meal_type.strip())

    if max_prep_time_minutes is not None:
        conditions.append("(prep_time_minutes IS NOT NULL AND prep_time_minutes <= %s)")
        params.append(max_prep_time_minutes)

    if ingredient and ingredient.strip():
        conditions.append(
            "EXISTS (SELECT 1 FROM unnest(ingredients) AS ing WHERE ing ILIKE %s)"
        )
        params.append(f"%{ingredient.strip()}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"""
        SELECT id, name, meal_type, prep_time_minutes, ingredients, created_at
        FROM meals
        {where_clause}
        ORDER BY created_at DESC, id DESC
    """

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def delete_meal(meal_id: int) -> Optional[dict]:
    pool = get_db_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "DELETE FROM meals WHERE id = %s RETURNING id, name",
                (meal_id,),
            )
            row = await cur.fetchone()
            await conn.commit()
            return dict(row) if row else None
