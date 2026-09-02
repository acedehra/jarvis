"use client";

import React, { useRef, useEffect } from "react";
import { Sparkles, Check, X, ShieldAlert, Cpu } from "lucide-react";

export interface ProviderConfig {
  id: string;
  name: string;
  configured: boolean;
  default_model: string;
  models: string[];
}

export interface ModelsInfo {
  default_provider: string;
  default_model: string;
  providers: ProviderConfig[];
}

interface ModelSelectorPopoverProps {
  isOpen: boolean;
  onClose: () => void;
  modelsInfo: ModelsInfo | null;
  selectedProvider?: string;
  selectedModel?: string;
  onSelectModel: (provider?: string, model?: string) => void;
}

export default function ModelSelectorPopover({
  isOpen,
  onClose,
  modelsInfo,
  selectedProvider,
  selectedModel,
  onSelectModel,
}: ModelSelectorPopoverProps) {
  const popoverRef = useRef<HTMLDivElement>(null);

  const isDefault = !selectedModel;
  const defaultModelName = modelsInfo?.default_model || "gemini-3.1-flash-lite";

  // Handle clicking outside to close
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen, onClose]);

  // Handle Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm sm:items-end sm:justify-center sm:pb-24">
      <div
        ref={popoverRef}
        className="w-full max-w-lg bg-slate-900 border border-slate-800/90 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[85vh]"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800/80 bg-slate-950/40">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-teal-400" />
            <h2 className="text-sm font-semibold text-slate-100">LLM Model Configuration</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="p-4 space-y-4 overflow-y-auto">
          {/* Default Option Card */}
          <div>
            <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-2 px-1">
              System Recommendation
            </div>
            <button
              onClick={() => {
                onSelectModel(undefined, undefined);
                onClose();
              }}
              className={`w-full text-left p-3.5 rounded-xl border transition-all flex items-start justify-between cursor-pointer ${
                isDefault
                  ? "bg-teal-500/10 border-teal-500/50 shadow-sm shadow-teal-500/10"
                  : "bg-slate-950/40 border-slate-800/80 hover:bg-slate-800/50 hover:border-slate-700"
              }`}
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-teal-400" />
                  <span className="text-xs font-semibold text-slate-100">System Default (Auto)</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-500/20 text-teal-300 font-mono">
                    {defaultModelName}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Uses the server-configured default model. High performance, zero setup, and fully optimized for tools and MCP runtime.
                </p>
              </div>
              {isDefault && (
                <div className="p-1 rounded-full bg-teal-500/20 text-teal-400 mt-0.5">
                  <Check className="w-3.5 h-3.5" />
                </div>
              )}
            </button>
          </div>

          {/* Model Overrides Grouped by Provider */}
          <div>
            <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-2 px-1">
              Override for this Session
            </div>

            <div className="space-y-3">
              {modelsInfo?.providers.map((prov) => {
                const isConfigured = prov.configured;

                return (
                  <div
                    key={prov.id}
                    className="p-3 bg-slate-950/40 border border-slate-800/70 rounded-xl space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-slate-200">{prov.name}</span>
                        {isConfigured ? (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            Ready
                          </span>
                        ) : (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1">
                            <ShieldAlert className="w-2.5 h-2.5" /> No API Key
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-1 gap-1.5">
                      {prov.models.map((m) => {
                        const isSelected = selectedProvider === prov.id && selectedModel === m;

                        return (
                          <button
                            key={m}
                            disabled={!isConfigured}
                            onClick={() => {
                              onSelectModel(prov.id, m);
                              onClose();
                            }}
                            className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-mono transition-all text-left ${
                              !isConfigured
                                ? "opacity-40 cursor-not-allowed bg-slate-900/40 text-slate-500"
                                : isSelected
                                ? "bg-teal-500/20 text-teal-200 border border-teal-500/40 font-semibold"
                                : "bg-slate-900/60 hover:bg-slate-800/80 text-slate-300 hover:text-white cursor-pointer"
                            }`}
                          >
                            <span className="truncate">{m}</span>
                            {isSelected && <Check className="w-3.5 h-3.5 text-teal-400 flex-shrink-0" />}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-800/80 bg-slate-950/60 flex items-center justify-between text-[11px] text-slate-400">
          <span>Overrides apply only to the active chat session.</span>
          {selectedModel && (
            <button
              onClick={() => {
                onSelectModel(undefined, undefined);
                onClose();
              }}
              className="text-xs text-rose-400 hover:text-rose-300 transition-colors font-medium cursor-pointer"
            >
              Reset to Default
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
