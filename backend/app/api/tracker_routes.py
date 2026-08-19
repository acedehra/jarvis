import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.services.tracker import (
    create_or_update_record,
    query_records,
    aggregate_records,
    update_record_status,
    delete_record,
    get_collections_summary,
    get_gas_analytics,
)

logger = logging.getLogger("tracker_routes")

router = APIRouter()


class RecordCreateRequest(BaseModel):
    collection: str = Field(..., description="Collection name, e.g. 'expense', 'todo', 'bookmark', 'reminder'")
    title: str = Field(..., description="Record title or short description")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary JSON metadata")
    event_date: Optional[str] = Field(None, description="ISO datetime string for due dates, expense date, etc.")
    user_id: str = Field("default_user", description="Owner user ID")


class RecordUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, description="Updated title")
    collection: Optional[str] = Field(None, description="Updated collection name")
    data: Optional[Dict[str, Any]] = Field(None, description="Updated JSON metadata fields")
    event_date: Optional[str] = Field(None, description="Updated ISO datetime")
    status: Optional[str] = Field(None, description="Shortcut to update data.status")
    user_id: str = Field("default_user", description="Owner user ID")


@router.get("/records", tags=["Tracker"])
async def list_records(
    collection: Optional[str] = Query(None, description="Filter by collection name"),
    search: Optional[str] = Query(None, description="Full-text search query"),
    date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD for start of period"),
    date_to: Optional[str] = Query(None, description="ISO date YYYY-MM-DD for end of period"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user_id: str = Query("default_user", description="User ID"),
):
    """
    Retrieve stored records with optional collection, date, and keyword filtering.
    """
    try:
        records = await query_records(
            user_id=user_id,
            collection=collection,
            date_from=date_from,
            date_to=date_to,
            search_query=search,
            limit=limit,
            offset=offset,
        )
        return {
            "status": "success",
            "count": len(records),
            "records": records,
        }
    except Exception as e:
        logger.error(f"Error querying tracker records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/records", tags=["Tracker"])
async def create_record(payload: RecordCreateRequest):
    """
    Create a new tracking record.
    """
    try:
        record = await create_or_update_record(
            collection=payload.collection,
            title=payload.title,
            data=payload.data,
            event_date=payload.event_date,
            user_id=payload.user_id,
        )
        return {"status": "success", "record": record}
    except Exception as e:
        logger.error(f"Error creating tracker record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/records/{record_id}", tags=["Tracker"])
async def update_record(record_id: str, payload: RecordUpdateRequest):
    """
    Update an existing tracking record.
    """
    try:
        updated = await update_record_status(
            record_id=record_id,
            user_id=payload.user_id,
            status=payload.status,
            updates=payload.data,
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Record '{record_id}' not found.")
        return {"status": "success", "record": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating record '{record_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/records/{record_id}", tags=["Tracker"])
async def remove_record(record_id: str, user_id: str = Query("default_user")):
    """
    Delete a tracking record by ID.
    """
    try:
        deleted = await delete_record(record_id=record_id, user_id=user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Record '{record_id}' not found.")
        return {"status": "success", "message": f"Record '{record_id}' deleted."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting record '{record_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/aggregate", tags=["Tracker"])
async def calculate_aggregation(
    collection: str = Query("expense", description="Collection name"),
    calculation: str = Query("sum", description="Calculation: 'sum', 'avg', 'count', 'min', 'max'"),
    field: Optional[str] = Query("amount", description="Numeric field in JSON data"),
    group_by: Optional[str] = Query(None, description="Field to group results by, e.g. 'category'"),
    date_from: Optional[str] = Query(None, description="ISO date start"),
    date_to: Optional[str] = Query(None, description="ISO date end"),
    user_id: str = Query("default_user", description="User ID"),
):
    """
    Run high-precision SQL calculations (totals, averages, groupings) on records.
    """
    try:
        result = await aggregate_records(
            user_id=user_id,
            collection=collection,
            calculation=calculation,
            field=field,
            group_by=group_by,
            date_from=date_from,
            date_to=date_to,
        )
        return {"status": "success", "analytics": result}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error computing aggregation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections", tags=["Tracker"])
async def list_collections_summary(user_id: str = Query("default_user")):
    """
    Get a list of all distinct collections and their record counts.
    """
    try:
        summary = await get_collections_summary(user_id=user_id)
        return {"status": "success", "collections": summary}
    except Exception as e:
        logger.error(f"Error fetching collections summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gas-analytics", tags=["Tracker"])
async def get_gas_stats(user_id: str = Query("default_user")):
    """
    Retrieve aggregated fuel analytics (total cost, total gallons, avg price per gallon,
    latest odometer reading, average MPG, and station breakdowns).
    """
    try:
        analytics = await get_gas_analytics(user_id=user_id)
        return {"status": "success", "analytics": analytics}
    except Exception as e:
        logger.error(f"Error computing gas analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

