import os
import json
import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Type
from pydantic import BaseModel, Field, create_model

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from langchain_core.tools import BaseTool

logger = logging.getLogger("mcp")


def json_schema_to_pydantic(name: str, schema: dict) -> Type[BaseModel]:
    """
    Dynamically construct a Pydantic BaseModel from a JSON Schema.
    This enables proper LangChain tool schema generation.
    """
    if not schema or not isinstance(schema, dict):
        return create_model(name)

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    if not isinstance(properties, dict) or not properties:
        return create_model(name)

    fields = {}
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict
    }

    for field_name, field_info in properties.items():
        if not isinstance(field_info, dict):
            continue

        field_type_str = field_info.get("type", "string")
        if isinstance(field_type_str, list):
            # Resolve potential union types (e.g. ["string", "null"])
            non_null_types = [t for t in field_type_str if t != "null"]
            field_type_str = non_null_types[0] if non_null_types else "string"

        if field_type_str == "array":
            from typing import List
            items_info = field_info.get("items", {})
            if isinstance(items_info, dict):
                item_type_str = items_info.get("type", "string")
                if isinstance(item_type_str, list):
                    non_null_item_types = [t for t in item_type_str if t != "null"]
                    item_type_str = non_null_item_types[0] if non_null_item_types else "string"
                item_type = type_map.get(item_type_str, str)
            else:
                item_type = str
            field_type = List[item_type]
        else:
            field_type = type_map.get(field_type_str, Any)

        field_desc = field_info.get("description", "")
        default_val = field_info.get("default", None)

        if field_name in required:
            # Required parameter (no default)
            fields[field_name] = (field_type, Field(..., description=field_desc))
        else:
            # Optional parameter
            fields[field_name] = (field_type, Field(default=default_val, description=field_desc))

    if not fields:
        return create_model(name)

    return create_model(name, **fields)


class MCPTool(BaseTool):
    """
    LangChain tool wrapper around an MCP Tool call.
    """
    session: Any = Field(exclude=True)
    original_name: str

    model_config = {
        "arbitrary_types_allowed": True
    }

    async def _arun(self, **kwargs: Any) -> Any:
        try:
            # Strip out None values to prevent validation errors on MCP servers that expect optional fields to be omitted rather than null
            cleaned_kwargs = {k: v for k, v in kwargs.items() if v is not None}
            logger.info(f"Executing MCP tool '{self.original_name}' (via alias '{self.name}') with args: {cleaned_kwargs}")
            result = await self.session.call_tool(self.original_name, cleaned_kwargs)

            # Format the output blocks (e.g. text/image) to a standard string
            text_parts = []
            for content in result.content:
                if getattr(content, "type", None) == "text":
                    text_parts.append(content.text)
                else:
                    text_parts.append(str(content))
            output_str = "\n".join(text_parts)

            if getattr(result, "isError", False):
                return f"Error executing tool {self.original_name}: {output_str}"
            return output_str
        except Exception as e:
            logger.error(f"Exception executing MCP tool '{self.original_name}': {e}", exc_info=True)
            return f"Error executing tool {self.original_name}: {str(e)}"

    def _run(self, **kwargs: Any) -> Any:
        raise NotImplementedError("Use async execution (ainvoke) for MCP tools.")


class MCPManager:
    """
    Registry and lifecycle manager for all registered MCP servers.
    Reads server definitions from mcp_config.json, launches stdio subprocesses or
    connects to SSE endpoints, and registers their tools.
    Supports dynamic adding, updating, disconnecting, and status inspection at runtime.
    """
    def __init__(self):
        self.server_stacks: Dict[str, AsyncExitStack] = {}
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: List[BaseTool] = []
        self.server_configs: Dict[str, dict] = {}
        self.server_statuses: Dict[str, dict] = {}

    def _get_config_path(self) -> str:
        from app.core.config import settings
        config_path = settings.MCP_CONFIG_PATH
        if not os.path.isabs(config_path):
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            resolved_path = os.path.join(backend_dir, config_path)
            if not os.path.exists(resolved_path):
                resolved_path = os.path.abspath(config_path)
        else:
            resolved_path = config_path
        return resolved_path

    def load_config(self) -> dict:
        config_path = self._get_config_path()
        if not os.path.exists(config_path):
            return {"mcpServers": {}}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to parse MCP configuration file: {e}")
            return {"mcpServers": {}}

    def save_config(self, config_data: dict) -> bool:
        config_path = self._get_config_path()
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save MCP configuration file: {e}")
            return False

    async def start(self):
        config_path = self._get_config_path()
        logger.info(f"🔌 Loading MCP configurations from: {config_path}")
        config = self.load_config()
        mcp_servers = config.get("mcpServers", {})
        if not mcp_servers:
            logger.info("ℹ️  No external MCP servers configured in 'mcpServers'.")
            return

        for name, srv_config in mcp_servers.items():
            await self._init_server(name, srv_config)

    async def _init_server(self, name: str, srv_config: dict):
        # If server is already running, disconnect it first
        if name in self.sessions:
            await self._disconnect_server(name)

        self.server_configs[name] = srv_config
        url = srv_config.get("url")
        headers = srv_config.get("headers")

        stack = AsyncExitStack()
        discovered_tools = []

        try:
            if url:
                logger.info(f"🔌 Connecting to SSE MCP server '{name}' at {url}...")
                read_stream, write_stream = await stack.enter_async_context(
                    sse_client(url, headers=headers)
                )
                session = await stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()
                self.sessions[name] = session
                self.server_stacks[name] = stack
                logger.info(f"✅ Connected to SSE MCP server '{name}'. Discovering tools...")
            else:
                command = srv_config.get("command")
                if not command:
                    err_msg = f"Server config for '{name}' must specify either 'command' (stdio) or 'url' (sse)."
                    logger.error(f"❌ {err_msg}")
                    self.server_statuses[name] = {
                        "status": "error",
                        "error": err_msg,
                        "tools": []
                    }
                    return

                args = srv_config.get("args", [])
                env = os.environ.copy()
                config_env = srv_config.get("env", {})
                if isinstance(config_env, dict):
                    for k, v in config_env.items():
                        env[k] = str(v)

                logger.info(f"🔌 Starting stdio MCP server subprocess '{name}' ({command} {' '.join(args)})...")
                server_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=env
                )

                read_stream, write_stream = await stack.enter_async_context(
                    stdio_client(server_params)
                )
                session = await stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()
                self.sessions[name] = session
                self.server_stacks[name] = stack
                logger.info(f"✅ Started stdio MCP server '{name}'. Discovering tools...")

            # Query tools from the session
            mcp_tools_resp = await session.list_tools()
            tools_list = mcp_tools_resp.tools if hasattr(mcp_tools_resp, "tools") else mcp_tools_resp

            for m_tool in tools_list:
                prefixed_name = f"{name}__{m_tool.name}"
                args_schema = json_schema_to_pydantic(f"{prefixed_name}_args", m_tool.inputSchema)

                langchain_tool = MCPTool(
                    name=prefixed_name,
                    description=m_tool.description or "",
                    original_name=m_tool.name,
                    session=session,
                    args_schema=args_schema
                )
                self.tools.append(langchain_tool)
                discovered_tools.append({
                    "name": prefixed_name,
                    "original_name": m_tool.name,
                    "description": m_tool.description or ""
                })
                logger.info(f"  🛠️  [MCP] {prefixed_name} - {m_tool.description or 'Custom MCP tool'}")

            self.server_statuses[name] = {
                "status": "connected",
                "tools": discovered_tools,
                "error": None
            }
            logger.info(f"✅ MCP server '{name}' registered {len(discovered_tools)} tool(s).")

        except Exception as e:
            err_str = str(e)
            logger.error(f"❌ Failed to connect/start MCP server '{name}': {err_str}", exc_info=True)
            await stack.aclose()
            self.server_statuses[name] = {
                "status": "error",
                "error": err_str,
                "tools": []
            }

    async def _disconnect_server(self, name: str):
        logger.info(f"🔌 Disconnecting MCP server '{name}'...")
        if name in self.server_stacks:
            try:
                await self.server_stacks[name].aclose()
            except Exception as e:
                logger.warning(f"Error closing exit stack for server '{name}': {e}")
            del self.server_stacks[name]
        
        if name in self.sessions:
            del self.sessions[name]

        # Remove registered tools for this server
        self.tools = [t for t in self.tools if not getattr(t, "name", "").startswith(f"{name}__")]
        if name in self.server_statuses:
            del self.server_statuses[name]

    async def add_server(self, name: str, srv_config: dict, persist: bool = True) -> dict:
        """
        Dynamically add and connect to a new MCP server.
        """
        await self._init_server(name, srv_config)
        if persist:
            config = self.load_config()
            mcp_servers = config.get("mcpServers", {})
            mcp_servers[name] = srv_config
            config["mcpServers"] = mcp_servers
            self.save_config(config)
        return self.server_statuses.get(name, {"status": "unknown"})

    async def remove_server(self, name: str, persist: bool = True) -> bool:
        """
        Dynamically disconnect and remove an MCP server.
        """
        await self._disconnect_server(name)
        if name in self.server_configs:
            del self.server_configs[name]
        if persist:
            config = self.load_config()
            mcp_servers = config.get("mcpServers", {})
            if name in mcp_servers:
                del mcp_servers[name]
                config["mcpServers"] = mcp_servers
                self.save_config(config)
        return True

    async def reconnect_server(self, name: str) -> dict:
        """
        Reconnect an existing server using its current configuration.
        """
        config = self.load_config()
        mcp_servers = config.get("mcpServers", {})
        srv_config = mcp_servers.get(name) or self.server_configs.get(name)
        if not srv_config:
            return {"status": "error", "error": f"Server '{name}' configuration not found."}
        await self._init_server(name, srv_config)
        return self.server_statuses.get(name, {"status": "unknown"})

    def get_servers_status(self) -> Dict[str, dict]:
        """
        Return status and discovered tools for all configured servers.
        """
        config = self.load_config()
        mcp_servers = config.get("mcpServers", {})
        result = {}
        for name, srv_config in mcp_servers.items():
            status_info = self.server_statuses.get(name, {"status": "disconnected", "tools": [], "error": None})
            result[name] = {
                "name": name,
                "config": srv_config,
                "status": status_info["status"],
                "error": status_info.get("error"),
                "tools": status_info.get("tools", [])
            }
        return result

    def get_tools(self) -> List[BaseTool]:
        """
        Return the list of all registered MCP tools.
        """
        return self.tools

    async def stop(self):
        logger.info("🛑 Disconnecting all MCP servers and releasing resources...")
        for name, stack in list(self.server_stacks.items()):
            try:
                await stack.aclose()
            except Exception as e:
                logger.warning(f"⚠️ Error shutting down exit stack for '{name}': {e}")
        self.server_stacks.clear()
        self.sessions.clear()
        self.tools.clear()
        self.server_statuses.clear()
        logger.info("🛑 MCP shutdown complete.")


# Global instance of MCPManager
mcp_manager = MCPManager()

