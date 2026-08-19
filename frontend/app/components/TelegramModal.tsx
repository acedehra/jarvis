"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  X,
  Send,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Copy,
  Check,
  RefreshCw,
  MessageSquare,
  Shield,
  Clock,
  Sparkles,
  Smartphone
} from "lucide-react";

interface TelegramStatus {
  is_active: boolean;
  bot_info?: {
    id: number;
    username: string;
    first_name: string;
  } | null;
  has_token_configured: boolean;
  chat_id_configured: boolean;
  chat_id?: string | null;
}

interface TelegramModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiBaseUrl?: string;
}

export default function TelegramModal({
  isOpen,
  onClose,
  apiBaseUrl = "http://localhost:8000"
}: TelegramModalProps) {
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [testSending, setTestSending] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const samplePrompts = [
    "Spent $14.50 on lunch at Chipotle",
    "How much have I spent on food this month?",
    "Add buy HDMI cable to my to-do list",
    "Remind me tomorrow at 9:00 AM to check backups",
    "Save this link: https://github.com/langchain-ai",
    "What pending tasks do I have left?"
  ];

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/api/telegram/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (err) {
      console.error("Failed to fetch Telegram status:", err);
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
      setTestResult(null);
    }
  }, [isOpen, fetchStatus]);

  const handleSendTest = async () => {
    setTestSending(true);
    setTestResult(null);
    try {
      const res = await fetch(`${apiBaseUrl}/api/telegram/test-message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: "🔔 Test notification from J.A.R.V.I.S. Dashboard! Two-way Telegram integration is active. 🚀"
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setTestResult("✅ Test notification sent successfully to Telegram!");
      } else {
        setTestResult(`❌ Error: ${data.detail || "Failed to send test message"}`);
      }
    } catch (err: any) {
      setTestResult(`❌ Network error: ${err.message}`);
    } finally {
      setTestSending(false);
    }
  };

  const copyToClipboard = async (text: string, idx: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(idx);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  if (!isOpen) return null;

  const isActive = status?.is_active;
  const botUsername = status?.bot_info?.username;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 w-full max-w-2xl rounded-2xl shadow-2xl flex flex-col overflow-hidden text-slate-100 font-sans max-h-[90vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-tr from-sky-500 to-blue-600 rounded-xl shadow-lg shadow-sky-500/10">
              <Send className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
                Telegram Two-Way Assistant
                {isActive ? (
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    Active & Listening
                  </span>
                ) : (
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700 font-medium">
                    Listener Inactive
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-400">
                Log expenses, track tasks, and query your database directly from Telegram.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchStatus}
              disabled={loading}
              className="p-2 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/40 text-slate-300 transition-colors"
              title="Refresh Status"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-sky-400" : ""}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/40 text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 scrollbar-thin">
          
          {/* Status & Connection Card */}
          <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase font-bold text-slate-400 tracking-wider flex items-center gap-1.5">
                <Smartphone className="w-3.5 h-3.5 text-sky-400" />
                Bot Connection Details
              </span>
              {botUsername && (
                <a
                  href={`https://t.me/${botUsername}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-sky-400 hover:text-sky-300 flex items-center gap-1 font-semibold underline underline-offset-2"
                >
                  <span>Open @{botUsername}</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-slate-900/80 border border-slate-800/80 rounded-lg space-y-1">
                <span className="text-slate-500 text-[10px] uppercase font-bold block">Bot Token</span>
                <span className="font-mono text-slate-200 block truncate">
                  {status?.has_token_configured ? "•••••••••••• (Configured ✓)" : "Not Configured in .env"}
                </span>
              </div>

              <div className="p-3 bg-slate-900/80 border border-slate-800/80 rounded-lg space-y-1">
                <span className="text-slate-500 text-[10px] uppercase font-bold block">Authorized Chat ID</span>
                <span className="font-mono text-slate-200 block truncate">
                  {status?.chat_id ? `${status.chat_id} (Restricted 🔒)` : "Open to all incoming chats"}
                </span>
              </div>
            </div>

            {/* Test Message Dispatcher */}
            <div className="pt-1 flex items-center justify-between gap-3">
              <span className="text-xs text-slate-400">
                Verify that your bot can send outbound alerts to Telegram:
              </span>
              <button
                onClick={handleSendTest}
                disabled={testSending}
                className="px-3.5 py-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold rounded-lg text-xs flex items-center gap-1.5 transition-all shadow-md shadow-sky-600/20 active:scale-95 flex-shrink-0"
              >
                {testSending ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                <span>Send Test Alert</span>
              </button>
            </div>

            {testResult && (
              <div className={`p-2.5 rounded-lg text-xs border ${
                testResult.startsWith("✅")
                  ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                  : "bg-rose-500/10 border-rose-500/20 text-rose-300"
              }`}>
                {testResult}
              </div>
            )}
          </div>

          {/* Prompt Cheat Sheet */}
          <div className="space-y-2.5">
            <span className="text-xs uppercase font-bold text-slate-400 tracking-wider block flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-teal-400" />
              Try Saying These on Telegram
            </span>
            <div className="grid grid-cols-1 gap-2">
              {samplePrompts.map((prompt, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2.5 bg-slate-950/40 border border-slate-800/80 hover:border-slate-700/80 rounded-xl transition-all group"
                >
                  <span className="text-xs text-slate-300 font-mono">
                    &ldquo;{prompt}&rdquo;
                  </span>
                  <button
                    onClick={() => copyToClipboard(prompt, idx)}
                    className="p-1.5 text-slate-500 hover:text-slate-200 rounded-lg hover:bg-slate-800 transition-colors"
                    title="Copy text"
                  >
                    {copiedIndex === idx ? (
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Setup Guide */}
          <div className="p-4 bg-slate-950/40 border border-slate-800/80 rounded-xl space-y-2 text-xs text-slate-400">
            <span className="font-bold text-slate-200 block flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-amber-400" />
              How to setup Telegram credentials
            </span>
            <ol className="list-decimal list-inside space-y-1 text-slate-400">
              <li>Message <strong className="text-slate-200">@BotFather</strong> on Telegram to create a bot and get a token.</li>
              <li>Paste the token in <code className="px-1 py-0.5 bg-slate-800 text-sky-300 rounded font-mono">backend/.env</code> as <code className="px-1 py-0.5 bg-slate-800 text-sky-300 rounded font-mono">TELEGRAM_BOT_TOKEN</code>.</li>
              <li>Message your bot with <code className="px-1 py-0.5 bg-slate-800 text-sky-300 rounded font-mono">/start</code> to receive your Chat ID, then add it to <code className="px-1 py-0.5 bg-slate-800 text-sky-300 rounded font-mono">TELEGRAM_CHAT_ID</code>.</li>
            </ol>
          </div>

        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 bg-slate-950/60 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold rounded-xl text-xs transition-colors"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
}
