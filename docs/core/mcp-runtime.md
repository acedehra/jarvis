# Dynamic Model Context Protocol (MCP) Runtime

J.A.R.V.I.S. features full implementation of Anthropic's **Model Context Protocol (MCP)**, standardizing how AI systems connect to external data sources and local developer tools.

---

## 🔌 What is MCP?

The Model Context Protocol (MCP) is an open standard that allows AI agents to discover, inspect, and invoke tools exposed by external servers.

---

## ⚙️ Transport Types Supported

J.A.R.V.I.S. supports both standard MCP transport protocols:

### 1. `stdio` (Local Subprocesses)
Spawns local executable commands (e.g. Node CLI packages, Python scripts, Git servers) communicating via standard input/output streams.

**Example `mcp_config.json`:**
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/ace/Documents/projects"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxxxxxxxxxxx"
      }
    }
  }
}
```

### 2. `sse` (Remote HTTP Server-Sent Events)
Connects to distributed remote tool servers running over HTTP/HTTPS with bi-directional streaming.

```json
{
  "mcpServers": {
    "remote_analytics": {
      "url": "https://mcp.internal.company.com/sse",
      "headers": {
        "Authorization": "Bearer sse_token_xyz"
      }
    }
  }
}
```

---

## ⚡ Dynamic Runtime Tool Binding

When an MCP server is connected:
1. J.A.R.V.I.S. calls `list_tools()` on the server to retrieve raw JSON schemas.
2. The `MCPManager` converts JSON Schemas into dynamic LangChain `StructuredTool` instances.
3. Tools are hot-bound to the active LangGraph model without restarting the FastAPI backend or dropping active WebSocket connections.

---

## 🖥️ Management via Web UI

The Next.js Web Dashboard includes a dedicated **MCP Management Modal**:
- View all configured servers and connection statuses.
- Inspect registered tool names, parameter schemas, and descriptions.
- Connect, disconnect, or add new servers at runtime.
