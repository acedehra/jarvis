"use client";

import React, { useState, useEffect } from "react";
import {
  Server,
  Cpu,
  Plus,
  Trash2,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Terminal,
  Globe,
  ChevronDown,
  ChevronRight,
  X,
  Sparkles,
  Layers,
  Key
} from "lucide-react";
import { authFetch } from "../utils/auth";

interface McpToolInfo {
  name: string;
  original_name: string;
  description: string;
}

interface McpServerConfig {
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
}

interface McpServer {
  name: string;
  config: McpServerConfig;
  status: "connected" | "error" | "disconnected";
  error?: string | null;
  tools: McpToolInfo[];
}

interface McpManagementModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiBaseUrl?: string;
}

export default function McpManagementModal({
  isOpen,
  onClose,
  apiBaseUrl = "http://localhost:8000"
}: McpManagementModalProps) {
  const [servers, setServers] = useState<Record<string, McpServer>>({});
  const [totalTools, setTotalTools] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [expandedServer, setExpandedServer] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState<boolean>(false);

  // Form State
  const [serverName, setServerName] = useState("");
  const [transport, setTransport] = useState<"stdio" | "sse">("stdio");
  const [command, setCommand] = useState("");
  const [argsStr, setArgsStr] = useState("");
  const [envPairs, setEnvPairs] = useState<{ key: string; value: string }[]>([]);
  const [url, setUrl] = useState("");
  const [headerPairs, setHeaderPairs] = useState<{ key: string; value: string }[]>([]);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchServers = async () => {
    setLoading(true);
    try {
      const res = await authFetch(`${apiBaseUrl}/api/mcp/servers`);
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const data = await res.json();
      if (data.status === "success") {
        setServers(data.servers || {});
        setTotalTools(data.total_tools || 0);
      }
    } catch (err: any) {
      console.error("Failed to fetch MCP servers:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchServers();
    }
  }, [isOpen]);

  const handleAddServer = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const name = serverName.trim().toLowerCase();
    if (!name) {
      setFormError("Server name is required.");
      return;
    }

    let payload: any = { name, transport };

    if (transport === "stdio") {
      if (!command.trim()) {
        setFormError("Command is required for stdio transport.");
        return;
      }
      const args = argsStr.trim() ? argsStr.trim().split(/\s+/) : [];
      const env: Record<string, string> = {};
      envPairs.forEach(p => {
        if (p.key.trim()) env[p.key.trim()] = p.value;
      });

      payload.command = command.trim();
      payload.args = args;
      payload.env = env;
    } else {
      if (!url.trim()) {
        setFormError("URL is required for SSE transport.");
        return;
      }
      const headers: Record<string, string> = {};
      headerPairs.forEach(p => {
        if (p.key.trim()) headers[p.key.trim()] = p.value;
      });

      payload.url = url.trim();
      payload.headers = headers;
    }

    setActionLoading("add");
    try {
      const res = await authFetch(`${apiBaseUrl}/api/mcp/servers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to add server");

      // Reset form
      setServerName("");
      setCommand("");
      setArgsStr("");
      setEnvPairs([]);
      setUrl("");
      setHeaderPairs([]);
      setShowAddForm(false);
      await fetchServers();
    } catch (err: any) {
      setFormError(err.message || "An error occurred while adding the server.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteServer = async (name: string) => {
    if (!confirm(`Are you sure you want to remove MCP server '${name}'?`)) return;
    setActionLoading(`delete_${name}`);
    try {
      const res = await authFetch(`${apiBaseUrl}/api/mcp/servers/${name}`, {
        method: "DELETE"
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to delete server");
      }
      await fetchServers();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReconnectServer = async (name: string) => {
    setActionLoading(`reconnect_${name}`);
    try {
      const res = await authFetch(`${apiBaseUrl}/api/mcp/servers/${name}/reconnect`, {
        method: "POST"
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to reconnect server");
      }
      await fetchServers();
    } catch (err: any) {
      alert(`Error reconnecting: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                MCP Servers Management
                <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 font-mono">
                  {totalTools} Active Tools
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Connect external Model Context Protocol (MCP) servers to extend Jarvis capabilities.
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={fetchServers}
              disabled={loading}
              className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition"
              title="Refresh Servers"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">

          {/* Add New Server Button / Form Toggle */}
          {!showAddForm ? (
            <div className="flex justify-between items-center bg-slate-800/40 p-4 rounded-xl border border-slate-800">
              <div className="flex items-center space-x-3">
                <Sparkles className="w-5 h-5 text-purple-400" />
                <div>
                  <h4 className="text-sm font-medium text-slate-200">Register New Server</h4>
                  <p className="text-xs text-slate-400">Add stdio tools (npx, uvx) or SSE remote endpoints.</p>
                </div>
              </div>
              <button
                onClick={() => setShowAddForm(true)}
                className="flex items-center space-x-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium rounded-lg transition shadow-lg shadow-purple-600/20"
              >
                <Plus className="w-4 h-4" />
                <span>Add MCP Server</span>
              </button>
            </div>
          ) : (
            <form onSubmit={handleAddServer} className="bg-slate-800/60 p-5 rounded-xl border border-purple-500/30 space-y-4 animate-in slide-in-from-top-2 duration-200">
              <div className="flex justify-between items-center pb-2 border-b border-slate-700">
                <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                  <Server className="w-4 h-4 text-purple-400" />
                  New MCP Server Setup
                </h3>
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
              </div>

              {formError && (
                <div className="p-3 bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Server Identifier Name</label>
                  <input
                    type="text"
                    placeholder="e.g. homeassistant, github, sqlite"
                    value={serverName}
                    onChange={(e) => setServerName(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-purple-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Transport Type</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setTransport("stdio")}
                      className={`px-3 py-2 text-xs font-medium rounded-lg border flex items-center justify-center gap-2 transition ${
                        transport === "stdio"
                          ? "bg-purple-600/20 border-purple-500 text-purple-300"
                          : "bg-slate-900 border-slate-700 text-slate-400 hover:bg-slate-800"
                      }`}
                    >
                      <Terminal className="w-3.5 h-3.5" />
                      Stdio (Subprocess)
                    </button>
                    <button
                      type="button"
                      onClick={() => setTransport("sse")}
                      className={`px-3 py-2 text-xs font-medium rounded-lg border flex items-center justify-center gap-2 transition ${
                        transport === "sse"
                          ? "bg-purple-600/20 border-purple-500 text-purple-300"
                          : "bg-slate-900 border-slate-700 text-slate-400 hover:bg-slate-800"
                      }`}
                    >
                      <Globe className="w-3.5 h-3.5" />
                      Remote SSE
                    </button>
                  </div>
                </div>
              </div>

              {transport === "stdio" ? (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-slate-300 mb-1">Executable Command</label>
                      <input
                        type="text"
                        placeholder="uvx / npx / python"
                        value={command}
                        onChange={(e) => setCommand(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-purple-500"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-xs font-medium text-slate-300 mb-1">Arguments (Space separated)</label>
                      <input
                        type="text"
                        placeholder="mcp-server-homeassistant OR -y @modelcontextprotocol/server-everything"
                        value={argsStr}
                        onChange={(e) => setArgsStr(e.target.value)}
                        className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-purple-500 font-mono"
                      />
                    </div>
                  </div>

                  {/* Environment variables key-value */}
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="text-xs font-medium text-slate-300 flex items-center gap-1">
                        <Key className="w-3 h-3 text-purple-400" />
                        Environment Variables
                      </label>
                      <button
                        type="button"
                        onClick={() => setEnvPairs([...envPairs, { key: "", value: "" }])}
                        className="text-[11px] text-purple-400 hover:text-purple-300 flex items-center gap-1"
                      >
                        <Plus className="w-3 h-3" /> Add Var
                      </button>
                    </div>
                    {envPairs.map((pair, idx) => (
                      <div key={idx} className="flex gap-2 mb-2">
                        <input
                          type="text"
                          placeholder="KEY (e.g. HASS_TOKEN)"
                          value={pair.key}
                          onChange={(e) => {
                            const newPairs = [...envPairs];
                            newPairs[idx].key = e.target.value;
                            setEnvPairs(newPairs);
                          }}
                          className="w-1/2 px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-md text-xs text-slate-100 font-mono"
                        />
                        <input
                          type="text"
                          placeholder="VALUE"
                          value={pair.value}
                          onChange={(e) => {
                            const newPairs = [...envPairs];
                            newPairs[idx].value = e.target.value;
                            setEnvPairs(newPairs);
                          }}
                          className="w-1/2 px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-md text-xs text-slate-100 font-mono"
                        />
                        <button
                          type="button"
                          onClick={() => setEnvPairs(envPairs.filter((_, i) => i !== idx))}
                          className="text-slate-500 hover:text-red-400 px-1"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">SSE URL Endpoint</label>
                  <input
                    type="url"
                    placeholder="http://localhost:8000/sse"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 focus:outline-none focus:border-purple-500 font-mono"
                  />
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading === "add"}
                  className="px-4 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium rounded-lg transition flex items-center space-x-2"
                >
                  {actionLoading === "add" && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>Connect Server</span>
                </button>
              </div>
            </form>
          )}

          {/* Configured Server List */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Configured MCP Servers ({Object.keys(servers).length})
            </h3>

            {Object.keys(servers).length === 0 ? (
              <div className="text-center py-10 bg-slate-800/20 rounded-xl border border-dashed border-slate-800">
                <Server className="w-10 h-10 text-slate-600 mx-auto mb-2" />
                <p className="text-sm font-medium text-slate-400">No MCP servers registered yet</p>
                <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
                  Click "Add MCP Server" above to connect Home Assistant, GitHub, SQLite, or custom tool servers.
                </p>
              </div>
            ) : (
              Object.entries(servers).map(([name, srv]) => {
                const isExpanded = expandedServer === name;
                const isConnected = srv.status === "connected";
                const isError = srv.status === "error";

                return (
                  <div
                    key={name}
                    className="bg-slate-800/40 border border-slate-800 rounded-xl overflow-hidden transition hover:border-slate-700"
                  >
                    {/* Item Header */}
                    <div className="flex items-center justify-between p-4 bg-slate-800/20">
                      <div
                        className="flex items-center space-x-3 cursor-pointer flex-1"
                        onClick={() => setExpandedServer(isExpanded ? null : name)}
                      >
                        <button className="text-slate-400">
                          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </button>
                        <div className="p-2 rounded-lg bg-slate-900 border border-slate-800">
                          {srv.config.url ? (
                            <Globe className="w-4 h-4 text-blue-400" />
                          ) : (
                            <Terminal className="w-4 h-4 text-purple-400" />
                          )}
                        </div>
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="text-sm font-semibold text-slate-200 font-mono">{name}</span>
                            {isConnected && (
                              <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-medium flex items-center gap-1">
                                <CheckCircle2 className="w-3 h-3" /> Connected
                              </span>
                            )}
                            {isError && (
                              <span className="px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 text-[10px] font-medium flex items-center gap-1">
                                <AlertCircle className="w-3 h-3" /> Error
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-400 font-mono mt-0.5">
                            {srv.config.url
                              ? srv.config.url
                              : `${srv.config.command} ${(srv.config.args || []).join(" ")}`}
                          </p>
                        </div>
                      </div>

                      {/* Action Controls */}
                      <div className="flex items-center space-x-2">
                        <span className="text-xs text-slate-400 bg-slate-900 px-2.5 py-1 rounded-md border border-slate-800 font-mono">
                          {srv.tools.length} Tools
                        </span>
                        <button
                          onClick={() => handleReconnectServer(name)}
                          disabled={actionLoading === `reconnect_${name}`}
                          className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition"
                          title="Reconnect Server"
                        >
                          <RefreshCw className={`w-4 h-4 ${actionLoading === `reconnect_${name}` ? "animate-spin" : ""}`} />
                        </button>
                        <button
                          onClick={() => handleDeleteServer(name)}
                          disabled={actionLoading === `delete_${name}`}
                          className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-slate-800 rounded-lg transition"
                          title="Remove Server"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    {/* Expandable Details Body */}
                    {isExpanded && (
                      <div className="p-4 border-t border-slate-800 bg-slate-900/40 space-y-3 text-xs">
                        {srv.error && (
                          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-300 font-mono overflow-x-auto">
                            <strong>Connection Error:</strong> {srv.error}
                          </div>
                        )}

                        <div>
                          <h5 className="font-medium text-slate-300 mb-2 flex items-center gap-1.5">
                            <Layers className="w-3.5 h-3.5 text-purple-400" />
                            Discovered MCP Tools ({srv.tools.length})
                          </h5>
                          {srv.tools.length === 0 ? (
                            <p className="text-slate-500 italic">No tools discovered from this server.</p>
                          ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                              {srv.tools.map((t) => (
                                <div
                                  key={t.name}
                                  className="p-2.5 bg-slate-900/80 border border-slate-800 rounded-lg space-y-1"
                                >
                                  <div className="font-mono text-purple-300 font-medium text-[11px] truncate">
                                    {t.name}
                                  </div>
                                  <div className="text-slate-400 text-[11px] line-clamp-2">
                                    {t.description || "No description provided."}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
