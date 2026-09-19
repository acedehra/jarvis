import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from fastmcp import FastMCP, Client
from langchain.mcp import MCPAdapter

from app.main import app
from app.services.mcp import MCPManager


class TestMCPService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = MCPManager()

    async def asyncTearDown(self):
        await self.manager.stop()

    async def test_empty_config(self):
        with patch.object(self.manager, "load_config", return_value={"mcpServers": {}}):
            await self.manager.start()
            self.assertEqual(len(self.manager.get_tools()), 0)
            self.assertEqual(self.manager.get_servers_status(), {})

    async def test_invalid_server_config_records_error(self):
        srv_config = {"transport": "stdio"}  # Missing command
        res = await self.manager.add_server("broken_server", srv_config, persist=False)
        self.assertEqual(res["status"], "error")
        status = self.manager.get_servers_status()
        self.assertIn("broken_server", status)
        self.assertEqual(status["broken_server"]["status"], "error")

    async def test_adapter_tool_discovery_and_execution(self):
        server = FastMCP("mock_weather")

        @server.tool()
        def get_weather(city: str) -> str:
            """Get current weather."""
            return f"Sunny in {city}"

        client = Client(server)
        adapter = MCPAdapter(client)
        tools = await adapter.list_tools()

        self.assertEqual(len(tools), 1)
        tool = tools[0]
        self.assertEqual(tool.name, "get_weather")
        
        # Test tool invocation
        result = await tool.ainvoke({"city": "Tokyo"})
        self.assertTrue(any("Sunny in Tokyo" in str(item) for item in result))
        await client.close()

    async def test_server_removal(self):
        self.manager.server_statuses["srv1"] = {"status": "connected", "tools": []}
        removed = await self.manager.remove_server("srv1", persist=False)
        self.assertTrue(removed)
        self.assertNotIn("srv1", self.manager.server_statuses)


class TestMCPRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.core import auth
        cls.test_key = "jarvis_sec_test_mcp_routes_key_123"
        auth._active_api_key = cls.test_key
        cls.client = TestClient(app)
        cls.auth_headers = {"X-API-Key": cls.test_key}

    def test_list_servers_endpoint(self):
        res = self.client.get("/api/mcp/servers", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("servers", data)
        self.assertIn("total_tools", data)

    def test_create_server_missing_command(self):
        payload = {
            "name": "test_stdio",
            "transport": "stdio"
            # command omitted
        }
        res = self.client.post("/api/mcp/servers", json=payload, headers=self.auth_headers)
        self.assertEqual(res.status_code, 400)
