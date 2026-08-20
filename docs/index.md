---
layout: home

hero:
  name: "J.A.R.V.I.S."
  text: "Autonomous Personal AI Operating System"
  tagline: "Engineered with LangGraph, FastAPI, Next.js 16, PostgreSQL & Model Context Protocol (MCP)"
  actions:
    - theme: brand
      text: Get Started
      link: /guide/getting-started
    - theme: alt
      text: System Architecture
      link: /guide/architecture
    - theme: alt
      text: View on GitHub ↗
      link: https://github.com/acedehra/jarvis

features:
  - icon: 🧠
    title: LangGraph State Machine
    details: Stateful multi-turn agent with typed states, asynchronous nodes, and persistent conversation checkpointing via AsyncPostgresSaver.
  - icon: 🧬
    title: Dual-Layer Memory
    details: Short-term dialogue compaction via RemoveMessage paired with asynchronous background reflection to extract persistent user facts.
  - icon: 🔌
    title: Dynamic MCP Runtime
    details: Hot-pluggable Model Context Protocol client connecting stdio subprocesses and remote SSE tools dynamically at runtime.
  - icon: 🛡️
    title: Human-in-the-Loop (HITL)
    details: Safety gates for high-stakes actions like Telegram messages, enabling real-time WebSocket approval, editing, or rejection.
  - icon: 📊
    title: Deterministic SQL Analytics
    details: Direct SQL aggregate calculation over JSONB collections (expenses, todos, reminders, bookmarks) eliminating arithmetic hallucinations.
  - icon: 📱
    title: Bidirectional Telegram Gateway
    details: Talk with J.A.R.V.I.S. on the go with two-way messaging, real-time tool execution, and background scheduled reminder alerts.
---

<style>
:root {
  --vp-home-hero-name-color: transparent;
  --vp-home-hero-name-background: -webkit-linear-gradient(120deg, #06b6d4 30%, #6366f1);
  --vp-c-brand-1: #06b6d4;
  --vp-c-brand-2: #0891b2;
  --vp-c-brand-3: #0e7490;
}
</style>
