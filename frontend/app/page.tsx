"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { 
  Send, 
  Sparkles, 
  Bot, 
  User, 
  Wifi, 
  WifiOff, 
  RefreshCw, 
  Terminal,
  Cpu,
  Zap,
  Plus,
  Trash2,
  MessageSquare,
  ChevronDown,
  ChevronRight,
  FileText,
  List,
  Search,
  Menu,
  X,
  Brain,
  Check,
  Copy,
  Server,
  Layers,
  Lock,
  LogOut,
  Volume2,
  VolumeX
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import McpManagementModal from "./components/McpManagementModal";
import TrackerModal from "./components/TrackerModal";
import TelegramModal from "./components/TelegramModal";
import ApiKeyGate from "./components/ApiKeyGate";
import { 
  getStoredApiKey, 
  clearStoredApiKey, 
  authFetch, 
  getAuthenticatedWsUrl, 
  getApiBaseUrl, 
  UNAUTHORIZED_EVENT 
} from "./utils/auth";


interface ToolCall {
  name: string;
  input: unknown;
  output?: string;
  status: "running" | "done" | "error";
}

interface Message {
  id: string;
  sender: "user" | "bot";
  text: string;
  timestamp: string;
  toolCalls?: ToolCall[];
  tokenUsage?: {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
  };
}

interface Thread {
  id: string;
  title: string;
  messages: Message[];
  provider: string;
  model: string;
  timestamp: string;
}

const PROVIDERS = [
  { id: "gemini", name: "Google Gemini", models: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.1-flash-lite"] },
  { id: "openai", name: "OpenAI", models: ["gpt-4o-mini", "gpt-4o", "o1-mini"] },
  { id: "anthropic", name: "Anthropic Claude", models: ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"] },
  { id: "openrouter", name: "OpenRouter", models: ["google/gemini-2.5-flash", "anthropic/claude-3.5-sonnet", "meta-llama/llama-3.3-70b-instruct"] },
];

interface CodeBlockProps {
  language: string;
  value: string;
}

export function CodeBlock({ language, value }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async () => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
  };

  const highlightCode = (code: string, _lang: string) => {
    if (!code) return "";
    
    const escapeHtml = (text: string) => {
      return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    };

    const escaped = escapeHtml(code);
    let highlighted = escaped;
    
    // Highlight comments: // or # or /* ... */
    highlighted = highlighted.replace(
      /(\/\/.*|#.*)/g,
      '<span class="text-slate-500 font-normal">$1</span>'
    );
    
    // Highlight strings: "..." or '...' or `...`
    highlighted = highlighted.replace(
      /(["'`])(.*?)\1/g,
      '<span class="text-amber-300">$1$2$1</span>'
    );

    // Highlight common programming language keywords
    const keywords = [
      "const", "let", "var", "function", "def", "import", "from", "return",
      "class", "async", "await", "if", "else", "for", "while", "in",
      "export", "default", "try", "except", "catch", "finally", "public",
      "private", "new", "this", "true", "false", "null", "undefined", "self", "as"
    ];
    
    const keywordRegex = new RegExp(`\\b(${keywords.join("|")})\\b`, "g");
    highlighted = highlighted.replace(
      keywordRegex,
      '<span class="text-teal-400 font-semibold">$1</span>'
    );

    return highlighted;
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-slate-800 bg-slate-950 font-mono text-xs shadow-lg max-w-full">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-900 border-b border-slate-800 text-[10px] text-slate-400 select-none">
        <span className="font-semibold uppercase tracking-wider text-teal-400">{language || "code"}</span>
        <button
          onClick={copyToClipboard}
          className="flex items-center gap-1 hover:text-white transition-all py-1 px-2 rounded hover:bg-slate-800 cursor-pointer active:scale-95"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-emerald-400" />
              <span className="text-emerald-400">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <div className="overflow-x-auto p-4 select-text max-h-[450px] scrollbar-thin">
        <pre className="m-0 leading-relaxed whitespace-pre font-mono">
          <code
            dangerouslySetInnerHTML={{
              __html: highlightCode(value, language),
            }}
          />
        </pre>
      </div>
    </div>
  );
}

function cleanTextForSpeech(text: string): string {
  if (!text) return "";
  let clean = String(text);
  // Strip code blocks and replace with brief cue
  clean = clean.replace(/```[\w\-]*\n[\s\S]*?\n```/g, " (code omitted) ");
  clean = clean.replace(/```[\s\S]*?```/g, " (code omitted) ");
  clean = clean.replace(/`([^`]+)`/g, "$1");
  clean = clean.replace(/!\[([^\]]*)\]\([^\)]+\)/g, "");
  clean = clean.replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1");
  clean = clean.replace(/https?:\/\/[^\s]+/g, "link");
  clean = clean.replace(/\|[^\n]+\|/g, " ");
  clean = clean.replace(/^[|\-:\s]+$/gm, "");
  clean = clean.replace(/^\s*#{1,6}\s+/gm, "");
  clean = clean.replace(/[*_~]{1,3}([^*_~]+)[*_~]{1,3}/g, "$1");
  clean = clean.replace(/^\s*>\s*/gm, "");
  clean = clean.replace(/^\s*[\*\-•]\s+/gm, "");
  clean = clean.replace(/\s+/g, " ").trim();
  return clean;
}

export default function Home() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [authChecked, setAuthChecked] = useState<boolean>(false);
  const [authError, setAuthError] = useState<string | undefined>(undefined);

  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string>("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  
  const [input, setInput] = useState("");
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});
  
  const [pendingApproval, setPendingApproval] = useState<{ toolCalls: any[] } | null>(null);
  const [draftMessage, setDraftMessage] = useState("");

  // Kokoro TTS Audio Controls & State
  const [autoSpeak, setAutoSpeak] = useState<boolean>(false);
  const [activeAudioMsgId, setActiveAudioMsgId] = useState<string | null>(null);
  const [loadingAudioMsgId, setLoadingAudioMsgId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const autoSpeakRef = useRef<boolean>(false);

  useEffect(() => {
    autoSpeakRef.current = autoSpeak;
  }, [autoSpeak]);

  useEffect(() => {
    const saved = localStorage.getItem("jarvis_auto_speak");
    if (saved === "true") {
      setAutoSpeak(true);
      autoSpeakRef.current = true;
    }
  }, []);

  const toggleAutoSpeak = () => {
    setAutoSpeak((prev) => {
      const next = !prev;
      autoSpeakRef.current = next;
      localStorage.setItem("jarvis_auto_speak", String(next));
      return next;
    });
  };

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setActiveAudioMsgId(null);
    setLoadingAudioMsgId(null);
  }, []);

  const playSpeech = useCallback(async (text: string, messageId?: string) => {
    if (!text) return;
    const clean = cleanTextForSpeech(text);
    if (!clean) return;

    if (messageId && activeAudioMsgId === messageId) {
      stopAudio();
      return;
    }

    stopAudio();
    if (messageId) {
      setLoadingAudioMsgId(messageId);
    }

    try {
      const res = await authFetch(`${getApiBaseUrl()}/api/tts/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: clean, response_format: "mp3" }),
      });

      if (!res.ok) {
        console.warn("TTS generation failed:", res.statusText);
        setLoadingAudioMsgId(null);
        return;
      }

      const blob = await res.blob();
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      if (messageId) {
        setActiveAudioMsgId(messageId);
        setLoadingAudioMsgId(null);
      }

      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        setActiveAudioMsgId(null);
        if (audioRef.current === audio) {
          audioRef.current = null;
        }
      };

      audio.onerror = () => {
        URL.revokeObjectURL(audioUrl);
        setActiveAudioMsgId(null);
        setLoadingAudioMsgId(null);
      };

      await audio.play();
    } catch (err) {
      console.error("Error playing TTS audio:", err);
      setActiveAudioMsgId(null);
      setLoadingAudioMsgId(null);
    }
  }, [activeAudioMsgId, stopAudio]);

  const handleApprovalAction = (action: "approve" | "reject" | "modify") => {
    if (!ws || !isConnected) return;
    
    setIsThinking(true);
    if (action === "approve") {
      ws.send(JSON.stringify({ action: "approve" }));
    } else if (action === "reject") {
      ws.send(JSON.stringify({ action: "reject" }));
    } else if (action === "modify") {
      ws.send(JSON.stringify({ action: "modify", modified_args: { message: draftMessage } }));
    }
    setPendingApproval(null);
  };
  
  const [memoryModalOpen, setMemoryModalOpen] = useState(false);
  const [mcpModalOpen, setMcpModalOpen] = useState(false);
  const [trackerModalOpen, setTrackerModalOpen] = useState(false);
  const [telegramModalOpen, setTelegramModalOpen] = useState(false);
  const [memories, setMemories] = useState<{ key: string; fact: string }[]>([]);


  // Check session storage authentication on mount
  useEffect(() => {
    const key = getStoredApiKey();
    if (key) {
      setIsAuthenticated(true);
    }
    setAuthChecked(true);

    const handleUnauthorized = () => {
      setIsAuthenticated(false);
      setAuthError("Session invalidated or API key rejected. Please re-authenticate.");
    };

    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => {
      window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    };
  }, []);

  const fetchMemories = async () => {
    try {
      const res = await authFetch(`${getApiBaseUrl()}/api/memories`);
      if (res.ok) {
        const data = await res.json();
        setMemories(data);
      }
    } catch (e) {
      console.error("Error fetching memories", e);
    }
  };

  const deleteMemory = async (key: string) => {
    try {
      const res = await authFetch(`${getApiBaseUrl()}/api/memories/${key}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setMemories((prev) => prev.filter((m) => m.key !== key));
      }
    } catch (e) {
      console.error("Error deleting memory", e);
    }
  };

  useEffect(() => {
    if (memoryModalOpen && isAuthenticated) {
      setTimeout(() => {
        fetchMemories();
      }, 0);
    }
  }, [memoryModalOpen, isAuthenticated]);
  
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTimeout(() => {
      const saved = localStorage.getItem("jarvis_threads");
      if (saved) {
        try {
          const parsed = JSON.parse(saved) as Thread[];
          if (parsed.length > 0) {
            setThreads(parsed);
            setActiveThreadId(parsed[0].id);
            return;
          }
        } catch (e) {
          console.error("Error loading threads", e);
        }
      }
      
      const defaultThread: Thread = {
        id: "default-thread",
        title: "J.A.R.V.I.S. Session",
        messages: [
          {
            id: "welcome",
            sender: "bot",
            text: "Welcome back, Sir. J.A.R.V.I.S. is online. How may I assist you today?",
            timestamp: new Date().toISOString(),
          },
        ],
        provider: "gemini",
        model: "gemini-2.5-flash",
        timestamp: new Date().toISOString()
      };
      setThreads([defaultThread]);
      setActiveThreadId(defaultThread.id);
    }, 0);
  }, []);

  const saveThreads = useCallback((updatedThreads: Thread[]) => {
    setThreads(updatedThreads);
    localStorage.setItem("jarvis_threads", JSON.stringify(updatedThreads));
  }, []);

  const activeThread = threads.find(t => t.id === activeThreadId) || threads[0];
  const messages = activeThread?.messages || [];
  const provider = activeThread?.provider || "gemini";
  const model = activeThread?.model || "gemini-2.5-flash";

  const updateActiveThreadConfig = useCallback((updates: Partial<Pick<Thread, "provider" | "model" | "title" | "messages">>) => {
    const updated = threads.map(t => {
      if (t.id === activeThreadId) {
        return {
          ...t,
          ...updates,
          timestamp: new Date().toISOString()
        };
      }
      return t;
    });
    saveThreads(updated);
  }, [threads, activeThreadId, saveThreads]);

  const connectWebSocket = () => {
    if (!activeThreadId || !getStoredApiKey()) return;
    if (ws) ws.close();
    
    setIsConnecting(true);
    const wsUrl = getAuthenticatedWsUrl(activeThreadId);
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      setIsConnected(true);
      setIsConnecting(false);
      setIsThinking(false);
    };

    socket.onmessage = (event) => {
      setIsThinking(false);
      try {
        const data = JSON.parse(event.data);
        if (data.type === "sensitive_tool_approval_required") {
          setIsThinking(false);
          const tcs = data.tool_calls || [];
          setPendingApproval({ toolCalls: tcs });
          const tgCall = tcs.find((tc: any) => tc.name === "send_telegram_message");
          if (tgCall && tgCall.args && tgCall.args.message) {
            setDraftMessage(tgCall.args.message);
          } else {
            setDraftMessage("");
          }
        } else if (data.type === "chunk") {
          let textChunk = "";
          if (typeof data.text === "string") {
            textChunk = data.text;
          } else if (data.text && typeof data.text === "object") {
            textChunk = data.text.text || JSON.stringify(data.text);
          }

          setThreads((prevThreads) => {
            const updated = prevThreads.map((t) => {
              if (t.id !== activeThreadId) return t;
              const currentMessages = [...t.messages];
              const last = currentMessages[currentMessages.length - 1];
              if (last && last.sender === "bot" && last.id.startsWith("bot-stream-")) {
                currentMessages[currentMessages.length - 1] = { ...last, text: last.text + textChunk };
              } else {
                currentMessages.push({
                  id: `bot-stream-${Date.now()}`,
                  sender: "bot" as const,
                  text: textChunk,
                  timestamp: new Date().toISOString()
                });
              }
              return { ...t, messages: currentMessages };
            });
            localStorage.setItem("jarvis_threads", JSON.stringify(updated));
            return updated;
          });
        } else if (data.type === "tool_start") {
          const newToolCall: ToolCall = { name: data.name, input: data.input, status: "running" };
          setThreads((prevThreads) => {
            const updated = prevThreads.map((t) => {
              if (t.id !== activeThreadId) return t;
              const currentMessages = [...t.messages];
              const last = currentMessages[currentMessages.length - 1];
              if (last && last.sender === "bot" && last.id.startsWith("bot-stream-")) {
                const toolCalls = last.toolCalls ? [...last.toolCalls, newToolCall] : [newToolCall];
                currentMessages[currentMessages.length - 1] = { ...last, toolCalls };
              } else {
                currentMessages.push({
                  id: `bot-stream-${Date.now()}`,
                  sender: "bot" as const,
                  text: "",
                  timestamp: new Date().toISOString(),
                  toolCalls: [newToolCall]
                });
              }
              return { ...t, messages: currentMessages };
            });
            localStorage.setItem("jarvis_threads", JSON.stringify(updated));
            return updated;
          });
        } else if (data.type === "tool_end") {
          setThreads((prevThreads) => {
            const updated = prevThreads.map((t) => {
              if (t.id !== activeThreadId) return t;
              const currentMessages = [...t.messages];
              const last = currentMessages[currentMessages.length - 1];
              if (last && last.sender === "bot" && last.id.startsWith("bot-stream-") && last.toolCalls) {
                const toolCalls = last.toolCalls.map((tc) => tc.name === data.name && tc.status === "running" ? { ...tc, status: "done" as const, output: data.output } : tc);
                currentMessages[currentMessages.length - 1] = { ...last, toolCalls };
              }
              return { ...t, messages: currentMessages };
            });
            localStorage.setItem("jarvis_threads", JSON.stringify(updated));
            return updated;
          });
        } else if (data.type === "tokens") {
          setThreads((prevThreads) => {
            const updated = prevThreads.map((t) => {
              if (t.id !== activeThreadId) return t;
              const currentMessages = [...t.messages];
              const last = currentMessages[currentMessages.length - 1];
              if (last && last.sender === "bot" && last.id.startsWith("bot-stream-")) {
                currentMessages[currentMessages.length - 1] = {
                  ...last,
                  tokenUsage: {
                    inputTokens: data.input_tokens,
                    outputTokens: data.output_tokens,
                    totalTokens: data.total_tokens
                  }
                };
              }
              return { ...t, messages: currentMessages };
            });
            localStorage.setItem("jarvis_threads", JSON.stringify(updated));
            return updated;
          });
        } else if (data.type === "done") {
          setIsThinking(false);
          if (autoSpeakRef.current) {
            setThreads((prevThreads) => {
              const active = prevThreads.find((t) => t.id === activeThreadId);
              if (active && active.messages.length > 0) {
                const lastMsg = active.messages[active.messages.length - 1];
                if (lastMsg && lastMsg.sender === "bot" && lastMsg.text) {
                  playSpeech(lastMsg.text, lastMsg.id);
                }
              }
              return prevThreads;
            });
          }
        } else if (data.type === "error") {
          setThreads((prevThreads) => {
            const updated = prevThreads.map((t) => {
              if (t.id !== activeThreadId) return t;
              return { ...t, messages: [...t.messages, { id: `bot-error-${Date.now()}`, sender: "bot" as const, text: `⚠️ ${data.text}`, timestamp: new Date().toISOString() }] };
            });
            localStorage.setItem("jarvis_threads", JSON.stringify(updated));
            return updated;
          });
        }
      } catch {
        setThreads((prevThreads) => {
          const updated = prevThreads.map((t) => {
            if (t.id !== activeThreadId) return t;
            return { ...t, messages: [...t.messages, { id: `bot-fallback-${Date.now()}`, sender: "bot" as const, text: event.data, timestamp: new Date().toISOString() }] };
          });
          localStorage.setItem("jarvis_threads", JSON.stringify(updated));
          return updated;
        });
      }
    };

    socket.onclose = (event) => { 
      setIsConnected(false); 
      setIsConnecting(false); 
      if (event.code === 1008) {
        clearStoredApiKey();
        setAuthError("Session rejected by server (1008 Policy Violation). Please verify your API key.");
      }
    };
    socket.onerror = () => { setIsConnected(false); setIsConnecting(false); };
    setWs(socket);
  };

  useEffect(() => {
    if (isAuthenticated) {
      setTimeout(() => {
        connectWebSocket();
      }, 0);
    }
    return () => { if (ws) ws.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeThreadId, isAuthenticated]);

  const handleScroll = () => {
    const container = containerRef.current;
    if (!container) return;
    const isAtBottom = 
      container.scrollHeight - container.scrollTop - container.clientHeight < 120;
    setAutoScroll(isAtBottom);
  };

  useEffect(() => {
    if (autoScroll) {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isThinking, autoScroll]);

  useEffect(() => {
    setTimeout(() => {
      setAutoScroll(true);
      chatEndRef.current?.scrollIntoView({ behavior: "auto" });
    }, 50);
  }, [activeThreadId]);

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !activeThread) return;
    setAutoScroll(true);
    const userMsgText = input.trim();
    const newUserMsg: Message = { id: `user-${Date.now()}`, sender: "user", text: userMsgText, timestamp: new Date().toISOString() };
    const isFirstMessage = messages.length === 1 && messages[0].id === "welcome";
    const newTitle = isFirstMessage ? userMsgText.slice(0, 24) + (userMsgText.length > 24 ? "..." : "") : activeThread.title;
    const updatedMessages = isFirstMessage ? [newUserMsg] : [...messages, newUserMsg];
    
    setThreads((prevThreads) => {
      const updated = prevThreads.map((t) => t.id === activeThreadId ? { ...t, title: newTitle, messages: updatedMessages, timestamp: new Date().toISOString() } : t);
      localStorage.setItem("jarvis_threads", JSON.stringify(updated));
      return updated;
    });
    setInput("");
    setIsThinking(true);
    if (ws && isConnected) {
      ws.send(JSON.stringify({ text: userMsgText, provider: provider, model: model }));
    } else {
      setIsThinking(false);
      setTimeout(() => {
        setThreads((prevThreads) => {
          const updated = prevThreads.map((t) => t.id === activeThreadId ? { ...t, messages: [...t.messages, { id: `bot-fallback-${Date.now()}`, sender: "bot" as const, text: `(Offline Mode) Unable to execute task: "${userMsgText}"`, timestamp: new Date().toISOString() }] } : t);
          localStorage.setItem("jarvis_threads", JSON.stringify(updated));
          return updated;
        });
      }, 800);
    }
  };

  const createNewThread = useCallback(() => {
    const newThread: Thread = {
      id: `thread-${Date.now()}`,
      title: "New Session",
      messages: [{ id: "welcome", sender: "bot", text: "Welcome back, Sir. J.A.R.V.I.S. is online. How may I assist you today?", timestamp: new Date().toISOString() }],
      provider: "gemini",
      model: "gemini-2.5-flash",
      timestamp: new Date().toISOString()
    };
    saveThreads([newThread, ...threads]);
    setActiveThreadId(newThread.id);
  }, [threads, saveThreads]);

  const deleteThread = useCallback(async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await authFetch(`${getApiBaseUrl()}/api/chat/sessions/${id}`, {
        method: "DELETE",
      });
    } catch (err) {
      console.error("Error deleting session on backend:", err);
    }
    const filtered = threads.filter(t => t.id !== id);
    if (filtered.length === 0) createNewThread();
    else {
      saveThreads(filtered);
      if (activeThreadId === id) setActiveThreadId(filtered[0].id);
    }
  }, [threads, activeThreadId, createNewThread, saveThreads]);

  const toggleToolExpand = useCallback((key: string) => setExpandedTools(prev => ({ ...prev, [key]: !prev[key] })), []);
  const getToolIcon = (name: string) => {
    if (name === "list_workspace_files") return <List className="w-3.5 h-3.5 text-blue-400" />;
    if (name === "read_workspace_file") return <FileText className="w-3.5 h-3.5 text-teal-400" />;
    if (name === "search_workspace_content") return <Search className="w-3.5 h-3.5 text-purple-400" />;
    if (name === "web_search") return <Search className="w-3.5 h-3.5 text-yellow-400" />;
    return <Terminal className="w-3.5 h-3.5 text-slate-400" />;
  };

  if (!authChecked) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-slate-950 text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin text-teal-400" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <ApiKeyGate
        onAuthenticated={() => {
          setIsAuthenticated(true);
          setAuthError(undefined);
        }}
        apiBaseUrl={getApiBaseUrl()}
        initialError={authError}
      />
    );
  }

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 font-sans selection:bg-teal-500/30 overflow-hidden">
      {sidebarOpen && (
        <aside className="w-72 bg-slate-900 border-r border-slate-800/80 flex flex-col h-full flex-shrink-0 z-30 transition-all">
          <div className="p-4 border-b border-slate-850 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-teal-400" />
              <span className="font-bold tracking-tight bg-gradient-to-r from-teal-400 to-emerald-400 bg-clip-text text-transparent text-sm">J.A.R.V.I.S. Core</span>
            </div>
            <button onClick={() => setSidebarOpen(false)} className="lg:hidden p-1 text-slate-400 hover:text-white"><X className="w-4 h-4" /></button>
          </div>
          <div className="p-3">
            <button onClick={createNewThread} className="w-full flex items-center justify-center gap-2 py-2 px-3 bg-gradient-to-tr from-teal-600 to-emerald-600 rounded-xl text-xs font-semibold hover:from-teal-500 hover:to-emerald-500 active:scale-[0.98]">
              <Plus className="w-4 h-4" /> New Session
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-2 space-y-1.5 scrollbar-thin">
            {threads.map((t) => (
              <div key={t.id} onClick={() => setActiveThreadId(t.id)} className={`group flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer ${t.id === activeThreadId ? "bg-slate-800/70 border-teal-500/30" : "hover:bg-slate-850/40"}`}>
                <div className="flex items-center gap-2 overflow-hidden flex-1">
                  <MessageSquare className={`w-3.5 h-3.5 ${t.id === activeThreadId ? "text-teal-400" : "text-slate-500"}`} />
                  <span className="text-xs truncate">{t.title}</span>
                </div>
                <button onClick={(e) => deleteThread(t.id, e)} className="opacity-0 group-hover:opacity-100 p-1 hover:text-rose-400"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            ))}
          </div>
        </aside>
      )}

      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <header className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-20">
          <div className="flex items-center gap-3">
            {!sidebarOpen && <button onClick={() => setSidebarOpen(true)} className="p-1.5 hover:bg-slate-800 rounded-lg"><Menu className="w-5 h-5" /></button>}
            <div className="p-1.5 bg-gradient-to-tr from-teal-500 to-emerald-500 rounded-lg"><Cpu className="w-5 h-5 text-slate-950" /></div>
            <div>
              <h1 className="text-sm font-bold tracking-tight bg-gradient-to-r from-teal-400 to-emerald-400 bg-clip-text text-transparent">J.A.R.V.I.S.</h1>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider">{activeThread?.title}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button 
              onClick={() => setTrackerModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/40 text-xs text-emerald-400 font-medium transition-all hover:scale-[1.02] active:scale-[0.98]"
              title="Open Universal Tracker & Second Brain"
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Tracker</span>
            </button>
            <button 
              onClick={() => setTelegramModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/40 text-xs text-sky-400 font-medium transition-all hover:scale-[1.02] active:scale-[0.98]"
              title="Telegram Integration & Alerts"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Telegram</span>
            </button>
            <button 
              onClick={() => setMemoryModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/40 text-xs text-teal-400 font-medium transition-all hover:scale-[1.02] active:scale-[0.98]"
              title="View what J.A.R.V.I.S. remembers about you"
            >
              <Brain className="w-3.5 h-3.5" />
              <span>Memory</span>
            </button>
            <button 
              onClick={() => setMcpModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-800/60 hover:bg-slate-700/60 border border-slate-700/40 text-xs text-purple-400 font-medium transition-all hover:scale-[1.02] active:scale-[0.98]"
              title="Manage MCP Tool Servers"
            >
              <Server className="w-3.5 h-3.5" />
              <span>MCP Servers</span>
            </button>

            {/* Auto-Speak Kokoro TTS Toggle */}
            <button
              onClick={toggleAutoSpeak}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer ${
                autoSpeak
                  ? "bg-teal-500/20 border-teal-500/50 text-teal-300 shadow-sm shadow-teal-500/20"
                  : "bg-slate-800/60 hover:bg-slate-700/60 border-slate-700/40 text-slate-400"
              }`}
              title={autoSpeak ? "Auto-Speak is ON: J.A.R.V.I.S. speaks responses aloud" : "Auto-Speak is OFF: Click to enable voice readout"}
            >
              {autoSpeak ? (
                <Volume2 className="w-3.5 h-3.5 text-teal-400 animate-pulse" />
              ) : (
                <VolumeX className="w-3.5 h-3.5 text-slate-500" />
              )}
              <span>Auto-Speak</span>
              <span className={`w-1.5 h-1.5 rounded-full ${autoSpeak ? "bg-teal-400" : "bg-slate-600"}`} />
            </button>

            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800/40 border border-slate-700/40 text-xs">
              {isConnected ? <><Wifi className="w-3 h-3 text-emerald-400 animate-pulse" /><span className="text-emerald-400 font-medium text-[11px]">Connected</span></> : <><WifiOff className="w-3 h-3 text-rose-400" /><span className="text-rose-400 font-medium text-[11px]">Offline</span></>}
              {!isConnected && <button onClick={connectWebSocket} disabled={isConnecting} className="ml-1.5"><RefreshCw className={`w-3 h-3 ${isConnecting ? "animate-spin" : ""}`} /></button>}
            </div>

            {/* Lock Session Button */}
            <button
              onClick={() => {
                clearStoredApiKey();
                setIsAuthenticated(false);
                setAuthError("Session locked. Please enter your API key to resume.");
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-800/60 hover:bg-rose-500/20 border border-slate-700/40 hover:border-rose-500/40 text-xs text-slate-300 hover:text-rose-300 font-medium transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
              title="Lock Session & Clear API Key"
            >
              <Lock className="w-3.5 h-3.5 text-teal-400" />
              <span>Lock Session</span>
            </button>
          </div>
        </header>

        <main 
          ref={containerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto p-6 space-y-6 max-w-4xl mx-auto w-full scrollbar-thin"
        >
          {messages.map((message) => (
            <div key={message.id} className={`flex gap-4 max-w-[90%] ${message.sender === "user" ? "ml-auto flex-row-reverse" : ""}`}>
              <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${message.sender === "user" ? "bg-teal-500/10 text-teal-400" : "bg-slate-800/80 text-teal-400"}`}>
                {message.sender === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>
              <div className="space-y-2 flex-1">
                {message.toolCalls?.map((tool, idx) => {
                  const toolKey = `${message.id}-${tool.name}-${idx}`;
                  const isExpanded = !!expandedTools[toolKey];
                  return (
                    <div key={idx} className="bg-slate-900/80 border border-slate-800/70 rounded-xl overflow-hidden text-xs max-w-2xl">
                      <div onClick={() => toggleToolExpand(toolKey)} className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-slate-850">
                        <div className="flex items-center gap-2">{getToolIcon(tool.name)} <span className="font-semibold">{tool.name.replace(/_/g, ' ')}</span></div>
                        <div className="flex items-center gap-1.5">{tool.status === "running" ? <RefreshCw className="w-3 h-3 animate-spin text-yellow-500" /> : <span className="text-emerald-400">Completed</span>}</div>
                      </div>
                      {isExpanded && tool.output && <div className="px-3 pb-3 pt-1"><pre className="p-2 bg-slate-950 rounded-lg text-[11px] overflow-auto">{tool.output}</pre></div>}
                    </div>
                  );
                })}
                {message.text && (
                  message.sender === "user" ? (
                    <div className={`px-4 py-3 rounded-2xl text-sm bg-gradient-to-br from-teal-600 to-emerald-600 text-white rounded-tr-none ml-auto whitespace-pre-wrap`}>
                      {typeof message.text === "string" 
                        ? message.text 
                        : (message.text as unknown as Record<string, string>).text || JSON.stringify(message.text)
                      }
                    </div>
                  ) : (
                    <div className="px-4 py-3 rounded-2xl text-sm bg-slate-900 border border-slate-800 rounded-tl-none text-slate-100 max-w-full overflow-hidden">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          code({ className, children, ...props }) {
                            const match = /language-(\w+)/.exec(className || '');
                            const isInline = !className;
                            const lang = match ? match[1] : '';
                            const codeValue = String(children).replace(/\n$/, '');
                            
                            if (!isInline && className) {
                              return <CodeBlock language={lang} value={codeValue} />;
                            }
                            
                            return (
                              <code className="px-1.5 py-0.5 rounded bg-slate-950 text-teal-300 font-mono text-xs border border-slate-800/80" {...props}>
                                {children}
                              </code>
                            );
                          },
                          ul({ children }) {
                            return <ul className="list-disc pl-5 my-2 space-y-1.5 text-slate-300">{children}</ul>;
                          },
                          ol({ children }) {
                            return <ol className="list-decimal pl-5 my-2 space-y-1.5 text-slate-300">{children}</ol>;
                          },
                          table({ children }) {
                            return (
                              <div className="overflow-x-auto my-3 border border-slate-800 rounded-xl max-w-full">
                                <table className="min-w-full divide-y divide-slate-800 bg-slate-950/40 text-xs">{children}</table>
                              </div>
                            );
                          },
                          thead({ children }) {
                            return <thead className="bg-slate-900/60">{children}</thead>;
                          },
                          tbody({ children }) {
                            return <tbody className="divide-y divide-slate-800/40">{children}</tbody>;
                          },
                          th({ children }) {
                            return <th className="px-4 py-2.5 text-left font-semibold text-slate-200 border-r border-slate-850 last:border-r-0">{children}</th>;
                          },
                          td({ children }) {
                            return <td className="px-4 py-2 text-slate-300 border-r border-slate-850 last:border-r-0">{children}</td>;
                          },
                          h1({ children }) {
                            return <h1 className="text-base font-bold text-slate-100 mt-4 mb-2 first:mt-0 pb-1 border-b border-slate-800">{children}</h1>;
                          },
                          h2({ children }) {
                            return <h2 className="text-sm font-bold text-slate-200 mt-3 mb-1.5 first:mt-0">{children}</h2>;
                          },
                          h3({ children }) {
                            return <h3 className="text-xs font-semibold text-slate-300 mt-2.5 mb-1 first:mt-0">{children}</h3>;
                          },
                          p({ children }) {
                            return <p className="leading-relaxed mb-2 last:mb-0 text-slate-250">{children}</p>;
                          },
                          a({ href, children }) {
                            return (
                              <a 
                                href={href} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                className="text-teal-400 hover:underline hover:text-teal-350 font-medium transition-all"
                              >
                                {children}
                              </a>
                            );
                          },
                          blockquote({ children }) {
                            return (
                              <blockquote className="border-l-4 border-teal-500/50 pl-3 my-2 text-slate-400 italic bg-teal-950/5 py-1.5 rounded-r">
                                {children}
                              </blockquote>
                            );
                          }
                        }}
                      >
                        {typeof message.text === "string" 
                          ? message.text 
                          : (message.text as unknown as Record<string, string>).text || JSON.stringify(message.text)
                        }
                      </ReactMarkdown>
                      <div className="mt-3 pt-2 border-t border-slate-800/60 flex items-center justify-between gap-2 text-[10px] text-slate-500 font-mono select-none">
                        {message.tokenUsage ? (
                          <div className="flex items-center gap-1.5 overflow-hidden text-ellipsis whitespace-nowrap">
                            <Zap className="w-3 h-3 text-amber-400/80 animate-pulse flex-shrink-0" />
                            <span className="font-semibold text-slate-400">Tokens: {message.tokenUsage.totalTokens}</span>
                            <span className="text-slate-700">•</span>
                            <span>Prompt: {message.tokenUsage.inputTokens}</span>
                            <span className="text-slate-700">•</span>
                            <span>Completion: {message.tokenUsage.outputTokens}</span>
                          </div>
                        ) : (
                          <div />
                        )}

                        <button
                          onClick={() => {
                            const raw = typeof message.text === "string" ? message.text : JSON.stringify(message.text);
                            playSpeech(raw, message.id);
                          }}
                          className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-sans font-medium transition-all cursor-pointer flex-shrink-0 ${
                            activeAudioMsgId === message.id
                              ? "bg-teal-500/20 text-teal-300 border border-teal-500/50 shadow-sm shadow-teal-500/20"
                              : "bg-slate-800/60 hover:bg-slate-700/60 text-slate-400 hover:text-teal-300 border border-slate-700/40"
                          }`}
                          title={activeAudioMsgId === message.id ? "Stop voice readout" : "Read aloud with J.A.R.V.I.S. voice"}
                        >
                          {loadingAudioMsgId === message.id ? (
                            <>
                              <RefreshCw className="w-3 h-3 animate-spin text-teal-400" />
                              <span>Synthesizing...</span>
                            </>
                          ) : activeAudioMsgId === message.id ? (
                            <>
                              <Volume2 className="w-3 h-3 text-teal-400 animate-pulse" />
                              <span>Speaking</span>
                            </>
                          ) : (
                            <>
                              <Volume2 className="w-3 h-3 text-slate-400" />
                              <span>Speak</span>
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>
          ))}
          {isThinking && (
            <div className="flex gap-4"><div className="w-8 h-8 rounded-full flex items-center justify-center bg-slate-800"><Bot className="w-4 h-4 text-teal-400" /></div><div className="px-4 py-3 bg-slate-900 rounded-2xl rounded-tl-none text-xs text-slate-400 animate-pulse">Thinking...</div></div>
          )}
          {pendingApproval && (
            <div className="flex gap-4 animate-in fade-in slide-in-from-bottom-4 duration-200">
              <div className="w-8 h-8 rounded-full flex items-center justify-center bg-amber-500/10 text-amber-400">
                <Brain className="w-4 h-4" />
              </div>
              <div className="flex-1 max-w-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-amber-500/30 rounded-2xl p-5 shadow-lg space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="flex h-2 w-2 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                    </span>
                    <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider font-mono">
                      Telegram Dispatch Authorization Required
                    </h3>
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">Action: send_telegram_message</span>
                </div>
                
                <p className="text-xs text-slate-350">
                  J.A.R.V.I.S. is requesting permission to transmit a message via Telegram. You can inspect and edit the transmission payload below:
                </p>

                <div className="space-y-1.5">
                  <label className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider block">Message Content</label>
                  <textarea
                    value={draftMessage}
                    onChange={(e) => setDraftMessage(e.target.value)}
                    rows={4}
                    className="w-full text-xs bg-slate-950/80 border border-slate-800 focus:border-amber-500/40 rounded-xl p-3 focus:outline-none text-slate-250 resize-none font-sans leading-relaxed"
                    placeholder="Enter message to send..."
                  />
                </div>

                <div className="flex gap-3 pt-1">
                  <button
                    onClick={() => handleApprovalAction("approve")}
                    className="flex-1 py-2 px-3 bg-gradient-to-tr from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 active:scale-[0.98] rounded-xl text-xs font-semibold text-white transition-all shadow-md shadow-emerald-950/40 cursor-pointer"
                  >
                    Approve & Send
                  </button>
                  <button
                    onClick={() => handleApprovalAction("modify")}
                    className="flex-1 py-2 px-3 bg-gradient-to-tr from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 active:scale-[0.98] rounded-xl text-xs font-semibold text-white transition-all shadow-md shadow-blue-950/40 cursor-pointer"
                  >
                    Modify & Send
                  </button>
                  <button
                    onClick={() => handleApprovalAction("reject")}
                    className="py-2 px-4 bg-slate-850 hover:bg-slate-800 text-xs font-semibold text-rose-400 hover:text-rose-300 border border-slate-800 hover:border-rose-950 rounded-xl transition-all cursor-pointer"
                  >
                    Reject (Cancel)
                  </button>
                </div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </main>

        <footer className="border-t border-slate-800/80 bg-slate-900/40 p-6 max-w-4xl mx-auto w-full">
          <div className="grid grid-cols-2 gap-3 mb-4">
            <select value={provider} onChange={(e) => updateActiveThreadConfig({ provider: e.target.value })} className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs">
              {PROVIDERS.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            <select value={model} onChange={(e) => updateActiveThreadConfig({ model: e.target.value })} className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs">
              {PROVIDERS.find((p) => p.id === provider)?.models.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <form onSubmit={handleSendMessage} className="flex gap-2">
            <input 
              value={input} 
              onChange={(e) => setInput(e.target.value)} 
              placeholder={pendingApproval ? "Authorize J.A.R.V.I.S. request below..." : "Message..."} 
              disabled={!!pendingApproval}
              className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed" 
            />
            <button 
              type="submit" 
              disabled={!!pendingApproval || !input.trim()} 
              className="p-3 bg-teal-600 rounded-xl disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </footer>
      </div>

      {/* Memory Management Modal */}
      {memoryModalOpen && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800/80 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl flex flex-col max-h-[80vh] animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80">
              <div className="flex items-center gap-2">
                <Brain className="w-5 h-5 text-teal-400" />
                <h2 className="text-sm font-bold tracking-tight text-slate-100">Long-Term Memory Vault</h2>
              </div>
              <button 
                onClick={() => setMemoryModalOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800/50"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto flex-1 space-y-4">
              <p className="text-xs text-slate-400 leading-relaxed">
                J.A.R.V.I.S. automatically extracts important facts and preferences from your conversations to personalize future interactions. Here is everything currently stored:
              </p>
              
              {memories.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-slate-500 border border-dashed border-slate-800 rounded-xl">
                  <Brain className="w-8 h-8 text-slate-600 mb-2 animate-pulse" />
                  <span className="text-xs">No memories stored yet.</span>
                  <span className="text-[10px] text-slate-600 mt-1">Talk to J.A.R.V.I.S. to build up its memory registry.</span>
                </div>
              ) : (
                <div className="space-y-2">
                  {memories.map((m) => (
                    <div 
                      key={m.key} 
                      className="flex items-start justify-between p-3.5 bg-slate-950/50 border border-slate-800/50 hover:border-slate-700/50 rounded-xl transition-all"
                    >
                      <div className="space-y-1 overflow-hidden flex-1 mr-3">
                        <span className="text-[10px] uppercase font-semibold text-teal-500 tracking-wider block font-mono">
                          {m.key.replace(/_/g, ' ')}
                        </span>
                        <span className="text-xs text-slate-200 block break-words">
                          {m.fact}
                        </span>
                      </div>
                      <button 
                        onClick={() => deleteMemory(m.key)}
                        className="p-1.5 text-slate-500 hover:text-rose-400 rounded-lg hover:bg-slate-900 transition-colors"
                        title="Forget this fact"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            <div className="px-6 py-4 bg-slate-950/40 border-t border-slate-800/80 flex justify-end">
              <button 
                onClick={() => setMemoryModalOpen(false)}
                className="px-4 py-2 bg-slate-850 hover:bg-slate-800 text-xs font-semibold rounded-xl text-slate-200 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MCP Management Modal */}
      <McpManagementModal
        isOpen={mcpModalOpen}
        onClose={() => setMcpModalOpen(false)}
        apiBaseUrl={getApiBaseUrl()}
      />

      {/* Universal Tracker Modal */}
      <TrackerModal
        isOpen={trackerModalOpen}
        onClose={() => setTrackerModalOpen(false)}
        apiBaseUrl={getApiBaseUrl()}
      />

      {/* Telegram Hub Modal */}
      <TelegramModal
        isOpen={telegramModalOpen}
        onClose={() => setTelegramModalOpen(false)}
        apiBaseUrl={getApiBaseUrl()}
      />
    </div>
  );
}

