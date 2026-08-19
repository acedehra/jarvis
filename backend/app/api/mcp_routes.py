import logging
from typing import Dict, List, Optional, Literal
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.services.mcp import mcp_manager

logger = logging.getLogger("mcp_routes")
router = APIRouter()


class McpServerPayload(BaseModel):
    name: str = Field(..., description="Unique name identifier for the MCP server")
    transport: Literal["stdio", "sse"] = Field("stdio", description="Connection transport type")
    command: Optional[str] = Field(None, description="Executable command for stdio servers (e.g. 'npx' or 'uvx')")
    args: Optional[List[str]] = Field(default_factory=list, description="Command line arguments for stdio servers")
    env: Optional[Dict[str, str]] = Field(default_factory=dict, description="Environment variables for stdio servers")
    url: Optional[str] = Field(None, description="SSE URL endpoint for remote servers")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="HTTP headers for SSE requests")


@router.get("/servers", summary="List all MCP servers and their current status")
async def list_mcp_servers():
    """
    Returns all configured MCP servers, their connection status, error details (if any),
    and discovered tools.
    """
    try:
        servers = mcp_manager.get_servers_status()
        return {
            "status": "success",
            "servers": servers,
            "total_tools": len(mcp_manager.get_tools())
        }
    except Exception as e:
        logger.error(f"Error listing MCP servers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list MCP servers: {str(e)}"
        )


@router.post("/servers", summary="Add and launch a new MCP server")
async def create_mcp_server(payload: McpServerPayload):
    """
    Add a new MCP server configuration and initialize its connection dynamically.
    """
    name = payload.name.strip().lower()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server name cannot be empty."
        )

    # Formulate server config dict
    if payload.transport == "sse":
        if not payload.url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL is required for SSE transport."
            )
        srv_config = {
            "url": payload.url,
            "headers": payload.headers or {}
        }
    else:
        if not payload.command:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Command is required for stdio transport."
            )
        srv_config = {
            "command": payload.command,
            "args": payload.args or [],
            "env": payload.env or {}
        }

    try:
        server_result = await mcp_manager.add_server(name, srv_config, persist=True)
        return {
            "status": "success",
            "message": f"MCP server '{name}' registered successfully.",
            "server": server_result
        }
    except Exception as e:
        logger.error(f"Error adding MCP server '{name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to launch MCP server '{name}': {str(e)}"
        )


@router.put("/servers/{name}", summary="Update an existing MCP server")
async def update_mcp_server(name: str, payload: McpServerPayload):
    """
    Update configuration for an existing MCP server and reconnect.
    """
    target_name = name.strip().lower()
    if payload.transport == "sse":
        if not payload.url:
            raise HTTPException(status_code=400, detail="URL is required for SSE transport.")
        srv_config = {"url": payload.url, "headers": payload.headers or {}}
    else:
        if not payload.command:
            raise HTTPException(status_code=400, detail="Command is required for stdio transport.")
        srv_config = {"command": payload.command, "args": payload.args or [], "env": payload.env or {}}

    try:
        server_result = await mcp_manager.add_server(target_name, srv_config, persist=True)
        return {
            "status": "success",
            "message": f"MCP server '{target_name}' updated and reconnected.",
            "server": server_result
        }
    except Exception as e:
        logger.error(f"Error updating MCP server '{target_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/servers/{name}", summary="Remove and disconnect an MCP server")
async def delete_mcp_server(name: str):
    """
    Disconnects and removes an MCP server configuration.
    """
    target_name = name.strip().lower()
    try:
        await mcp_manager.remove_server(target_name, persist=True)
        return {
            "status": "success",
            "message": f"MCP server '{target_name}' removed."
        }
    except Exception as e:
        logger.error(f"Error removing MCP server '{target_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servers/{name}/reconnect", summary="Reconnect an MCP server")
async def reconnect_mcp_server(name: str):
    """
    Attempts to re-establish connection to a disconnected or failed MCP server.
    """
    target_name = name.strip().lower()
    try:
        server_result = await mcp_manager.reconnect_server(target_name)
        return {
            "status": "success",
            "server": server_result
        }
    except Exception as e:
        logger.error(f"Error reconnecting MCP server '{target_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))
