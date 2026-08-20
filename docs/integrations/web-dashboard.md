# Next.js 16 Web Dashboard

The J.A.R.V.I.S. frontend is a modern, responsive web application engineered with **Next.js 16 (App Router)** and **React 19**.

---

## 🎨 User Interface Highlights

- **Real-Time Streaming**: High-throughput WebSocket connection streaming LLM tokens, tool call executions, and state changes with zero latency.
- **Dynamic Modals**:
  - 📊 **Tracker Modal**: View and filter records in `expenses`, `todos`, `reminders`, and `bookmarks` collections.
  - 🔌 **MCP Management Modal**: Inspect attached `stdio` and `sse` tool servers, check tool schemas, and trigger hot-reloads.
  - 📱 **Telegram Configuration Modal**: Manage bot connection parameters and chat verification.
  - 🛡️ **HITL Approval Dialog**: Inspect pending tool arguments, edit payloads inline, and approve/reject executions.
- **Modern Theme**: Fluid dark theme with sleek glassmorphism, responsive mobile layouts, and custom typography.

---

## 🛠️ Architecture & State Management

```
frontend/
├── app/
│   ├── components/
│   │   ├── ChatInterface.tsx      # WebSocket streaming client & message list
│   │   ├── McpManagementModal.tsx # Server & tool inspection modal
│   │   ├── TrackerModal.tsx       # Expense & task table browser
│   │   ├── TelegramModal.tsx      # Bot settings modal
│   │   └── HitlApprovalModal.tsx  # Interactive approval gate
│   ├── layout.tsx                 # Root layout & theme providers
│   └── page.tsx                   # Main dashboard view
├── next.config.ts                 # Next.js build & proxy configuration
└── package.json                   # Dependencies (Bun managed)
```

---

## ⚡ Running Locally

```bash
cd frontend
bun install
bun run dev
```

Visit [http://localhost:3000](http://localhost:3000) to open the dashboard.
