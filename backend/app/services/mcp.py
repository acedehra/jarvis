import os
import json
import logging
import warnings
from typing import Dict, List, Optional
from langchain_core.tools import BaseTool

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport, SSETransport
    from langchain.mcp import MCPAdapter

logger = logging.getLogger("mcp")


class MCPManager:
    """
    Registry and lifecycle manager for all registered MCP servers using LangChain's
    built-in MCP integration (langchain.mcp / FastMCP).

    Reads server definitions from mcp_config.json, launches stdio subprocesses or
    connects to SSE endpoints, adapts tools into first-class LangChain StructuredTools,
    and supports dynamic registering, disconnecting, updating, and health inspection.
    """
    def __init__(self):
        self.clients: Dict[str, Client] = {}
        self.adapters: Dict[str, MCPAdapter] = {}
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
        if name in self.clients:
            await self._disconnect_server(name)

        self.server_configs[name] = srv_config
        url = srv_config.get("url")
        headers = srv_config.get("headers")

        client: Optional[Client] = None
        discovered_tools: List[dict] = []

        try:
            if url:
                logger.info(f"🔌 Connecting to SSE MCP server '{name}' at {url}...")
                transport = SSETransport(url=url, headers=headers or {})
                client = Client(transport)
                adapter = MCPAdapter(client)
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
                transport = StdioTransport(
                    command=command,
                    args=args,
                    env=env
                )
                client = Client(transport)
                adapter = MCPAdapter(client)
                logger.info(f"✅ Initialized stdio MCP client '{name}'. Discovering tools...")

            # Discover tools via LangChain MCPAdapter
            server_tools = await adapter.list_tools()
            for tool in server_tools:
                orig_name = tool.name
                prefixed_name = f"{name}__{orig_name}"
                tool.name = prefixed_name
                self.tools.append(tool)
                discovered_tools.append({
                    "name": prefixed_name,
                    "original_name": orig_name,
                    "description": tool.description or ""
                })
                logger.info(f"  🛠️  [MCP] {prefixed_name} - {tool.description or 'Custom MCP tool'}")

            self.clients[name] = client
            self.adapters[name] = adapter
            self.server_statuses[name] = {
                "status": "connected",
                "tools": discovered_tools,
                "error": None
            }
            logger.info(f"✅ MCP server '{name}' registered {len(discovered_tools)} tool(s) via langchain[mcp].")

        except Exception as e:
            err_str = str(e)
            logger.error(f"❌ Failed to connect/start MCP server '{name}': {err_str}", exc_info=True)
            if client is not None:
                try:
                    await client.close()
                except Exception:
                    pass
            self.server_statuses[name] = {
                "status": "error",
                "error": err_str,
                "tools": []
            }

    async def _disconnect_server(self, name: str):
        logger.info(f"🔌 Disconnecting MCP server '{name}'...")
        if name in self.clients:
            try:
                await self.clients[name].close()
            except Exception as e:
                logger.warning(f"Error closing FastMCP client for server '{name}': {e}")
            del self.clients[name]

        if name in self.adapters:
            del self.adapters[name]

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
        all_servers = dict(config.get("mcpServers", {}))
        for name, cfg in self.server_configs.items():
            if name not in all_servers:
                all_servers[name] = cfg

        result = {}
        for name, srv_config in all_servers.items():
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
        for name in list(self.clients.keys()):
            await self._disconnect_server(name)
        self.clients.clear()
        self.adapters.clear()
        self.tools.clear()
        self.server_statuses.clear()
        logger.info("🛑 MCP shutdown complete.")


# Global instance of MCPManager
mcp_manager = MCPManager()


