"use client";

import React, { useState } from "react";
import { 
  KeyRound, 
  ShieldCheck, 
  ShieldAlert, 
  Eye, 
  EyeOff, 
  ArrowRight, 
  Loader2, 
  HelpCircle, 
  Clipboard, 
  Terminal, 
  FileCode, 
  Lock,
  Sparkles
} from "lucide-react";
import { setStoredApiKey, validateApiKey } from "../utils/auth";

interface ApiKeyGateProps {
  onAuthenticated: (apiKey: string) => void;
  apiBaseUrl?: string;
  initialError?: string;
}

export default function ApiKeyGate({
  onAuthenticated,
  apiBaseUrl,
  initialError
}: ApiKeyGateProps) {
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(initialError || null);
  const [showHelp, setShowHelp] = useState(false);
  const [pasted, setPasted] = useState(false);

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setApiKeyInput(text.trim());
        setPasted(true);
        setTimeout(() => setPasted(false), 2000);
      }
    } catch (e) {
      console.warn("Could not read from clipboard:", e);
    }
  };

  const handleUnlock = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!apiKeyInput.trim() || isValidating) return;

    setIsValidating(true);
    setErrorMessage(null);

    const validation = await validateApiKey(apiKeyInput, apiBaseUrl);
    setIsValidating(false);

    if (validation.success) {
      setStoredApiKey(apiKeyInput);
      onAuthenticated(apiKeyInput.trim());
    } else {
      setErrorMessage(validation.message || "Invalid API key. Please check your credentials.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950 overflow-y-auto">
      {/* Background glow & subtle cyber grid */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_20%,_rgba(20,184,166,0.15),_transparent_70%)] pointer-events-none" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#0f172a15_1px,transparent_1px),linear-gradient(to_bottom,#0f172a15_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      {/* Main Paywall Card */}
      <div className="relative w-full max-w-lg rounded-3xl bg-slate-900/90 border border-slate-800/80 shadow-2xl backdrop-blur-2xl p-6 sm:p-10 text-slate-100 transition-all duration-300">
        
        {/* Glow Accent Border Line */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-48 h-[2px] bg-gradient-to-r from-transparent via-teal-400 to-transparent" />

        {/* Header Section */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="relative mb-5">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-tr from-teal-500/20 via-cyan-500/10 to-indigo-500/20 border border-teal-500/40 flex items-center justify-center shadow-lg shadow-teal-500/20 group">
              <KeyRound className="w-10 h-10 text-teal-400 animate-pulse group-hover:scale-110 transition-transform duration-300" />
            </div>
            <div className="absolute -top-1 -right-1 flex h-4 w-4">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-4 w-4 bg-teal-500"></span>
            </div>
          </div>

          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-teal-500/10 border border-teal-500/30 text-teal-300 text-xs font-semibold tracking-wider uppercase mb-3">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Secure Neural Access Gate</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
            J.A.R.V.I.S.
          </h1>
          <p className="text-slate-400 text-sm mt-2 max-w-sm">
            Enter your API Key to initialize the session and connect to your autonomous assistant.
          </p>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-start gap-3 animate-in fade-in slide-in-from-top-2 duration-200">
            <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium">{errorMessage}</p>
            </div>
          </div>
        )}

        {/* Key Input Form */}
        <form onSubmit={handleUnlock} className="space-y-4">
          <div className="relative">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              API Authentication Key
            </label>
            
            <div className="relative flex items-center">
              <div className="absolute left-3.5 text-slate-500 pointer-events-none">
                <Lock className="w-4 h-4 text-slate-400" />
              </div>

              <input
                type={showKey ? "text" : "password"}
                value={apiKeyInput}
                onChange={(e) => {
                  setApiKeyInput(e.target.value);
                  if (errorMessage) setErrorMessage(null);
                }}
                placeholder="jarvis_sec_..."
                autoFocus
                disabled={isValidating}
                className="w-full pl-10 pr-24 py-3.5 bg-slate-950/80 border border-slate-700/70 focus:border-teal-400 focus:ring-2 focus:ring-teal-400/20 rounded-xl text-slate-100 placeholder:text-slate-600 font-mono text-sm tracking-wide transition-all outline-none"
              />

              <div className="absolute right-2 flex items-center gap-1">
                {/* Paste Button */}
                <button
                  type="button"
                  onClick={handlePaste}
                  title="Paste from clipboard"
                  className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
                >
                  <Clipboard className={`w-4 h-4 ${pasted ? "text-teal-400" : ""}`} />
                </button>

                {/* Show/Hide Toggle */}
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  title={showKey ? "Hide key" : "Show key"}
                  className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
                >
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={!apiKeyInput.trim() || isValidating}
            className="w-full mt-2 py-3.5 px-6 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 text-slate-950 shadow-lg shadow-teal-500/25 active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none transition-all duration-200 cursor-pointer"
          >
            {isValidating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-slate-950" />
                <span>Authenticating Neural Core...</span>
              </>
            ) : (
              <>
                <span>Unlock J.A.R.V.I.S.</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Help & Key Recovery Accordion */}
        <div className="mt-6 pt-6 border-t border-slate-800/80">
          <button
            type="button"
            onClick={() => setShowHelp(!showHelp)}
            className="w-full flex items-center justify-between text-xs text-slate-400 hover:text-slate-200 transition-colors py-1 cursor-pointer"
          >
            <span className="flex items-center gap-1.5 font-medium">
              <HelpCircle className="w-3.5 h-3.5 text-teal-400" />
              Where do I find my API Key?
            </span>
            <span className="text-teal-400 font-mono text-[11px]">
              {showHelp ? "Hide instructions" : "Show instructions"}
            </span>
          </button>

          {showHelp && (
            <div className="mt-3.5 p-4 rounded-xl bg-slate-950/70 border border-slate-800 space-y-3 text-xs text-slate-300 font-sans leading-relaxed animate-in fade-in duration-200">
              <div className="flex items-start gap-2.5">
                <Terminal className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-slate-100">1. First Backend Run</span>
                  <p className="text-slate-400 mt-0.5">
                    Check your backend terminal logs. Jarvis automatically generates a secure key on first launch and prints it in a highlighted banner.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <FileCode className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-slate-100">2. Persisted File</span>
                  <p className="text-slate-400 mt-0.5">
                    The key is saved inside <code className="px-1.5 py-0.5 rounded bg-slate-800 text-teal-300 font-mono text-[11px]">backend/.api_key</code>.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-2.5">
                <ShieldCheck className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-slate-100">3. Custom Configuration</span>
                  <p className="text-slate-400 mt-0.5">
                    You can set a custom key in <code className="px-1.5 py-0.5 rounded bg-slate-800 text-teal-300 font-mono text-[11px]">backend/.env</code> using <code className="text-slate-200 font-mono">API_KEY=...</code>.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Security Footer Notice */}
        <div className="mt-6 text-center text-[11px] text-slate-500 flex items-center justify-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-slate-500" />
          <span>Key is securely held in browser session memory only</span>
        </div>

      </div>
    </div>
  );
}
