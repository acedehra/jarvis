"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Plus,
  Minus,
  Trash2,
  RefreshCw,
  AlertTriangle,
  Sparkles,
  Beef,
  Milk,
  Leaf,
  Fish,
  Cookie,
  Snowflake,
  Droplet,
  Package,
  Utensils,
} from "lucide-react";
import { authFetch, getApiBaseUrl, getStoredApiKey } from "../utils/auth";
import ApiKeyGate from "../components/ApiKeyGate";

// --------------------------------------------------------------------------- types

export interface PantryItem {
  name: string;
  quantity: number;
  unit: string;
  category: string;
  expiry?: string | null;
  days_to_expiry?: number | null;
  id?: string;
}

export interface MissingIngredient {
  name: string;
  quantity?: string | null;
  required: boolean;
}

export interface MealSuggestion {
  name: string;
  summary: string;
  uses_expiring: boolean;
  missing_ingredients: MissingIngredient[];
}

export interface MealPlan {
  ok: boolean;
  generated: boolean;
  meals: MealSuggestion[];
  note: string;
}

export interface ExpiringItem {
  name: string;
  quantity: number;
  unit: string;
  expiry: string;
  days_to_expiry: number;
  alerted: boolean;
}

// --------------------------------------------------------------------------- helpers

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  produce: <Leaf className="w-4 h-4 text-green-400" />,
  dairy: <Milk className="w-4 h-4 text-sky-400" />,
  meat: <Beef className="w-4 h-4 text-rose-400" />,
  seafood: <Fish className="w-4 h-4 text-cyan-400" />,
  bakery: <Cookie className="w-4 h-4 text-amber-400" />,
  pantry: <Package className="w-4 h-4 text-slate-400" />,
  spice: <Sparkles className="w-4 h-4 text-yellow-400" />,
  frozen: <Snowflake className="w-4 h-4 text-blue-400" />,
  condiment: <Droplet className="w-4 h-4 text-orange-400" />,
  other: <Package className="w-4 h-4 text-slate-500" />,
};

const CATEGORIES = [
  "produce",
  "dairy",
  "meat",
  "seafood",
  "bakery",
  "pantry",
  "spice",
  "frozen",
  "condiment",
  "other",
];

const UNITS = ["items", "kg", "g", "lb", "oz", "l", "ml", "clove", "can", "bunch", "pack", "cup", "tbsp", "tsp"];

function expiryTone(d: number | null | undefined): { badge: string; label: string } {
  if (d === null || d === undefined) return { badge: "bg-slate-800 text-slate-400 border-slate-700", label: "no expiry" };
  if (d < 0) return { badge: "bg-rose-500/20 text-rose-300 border-rose-500/40", label: `expired ${Math.abs(d)}d ago` };
  if (d === 0) return { badge: "bg-orange-500/20 text-orange-300 border-orange-500/40", label: "expires today!" };
  if (d <= 3) return { badge: "bg-amber-500/20 text-amber-300 border-amber-500/40", label: `expires in ${d}d` };
  return { badge: "bg-slate-800/80 text-slate-300 border-slate-700", label: `expires in ${d}d` };
}

// --------------------------------------------------------------------------- page

export default function PantryPage() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => !!getStoredApiKey());
  const [items, setItems] = useState<PantryItem[]>([]);
  const [expiring, setExpiring] = useState<ExpiringItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Meal-plan state
  const [plan, setPlan] = useState<MealPlan | null>(null);
  const [planning, setPlanning] = useState(false);
  const [mealCount, setMealCount] = useState(3);

  // Add form
  const [showAdd, setShowAdd] = useState(false);
  const [formName, setFormName] = useState("");
  const [formQty, setFormQty] = useState("1");
  const [formUnit, setFormUnit] = useState("items");
  const [formCategory, setFormCategory] = useState("produce");
  const [formExpiry, setFormExpiry] = useState("");

  // Consume modal-ish inline
  const [consuming, setConsuming] = useState<PantryItem | null>(null);
  const [consumeQty, setConsumeQty] = useState("1");

  const apiBaseUrl = getApiBaseUrl();

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [invRes, expRes] = await Promise.all([
        authFetch(`${apiBaseUrl}/api/tracker/pantry`),
        authFetch(`${apiBaseUrl}/api/tracker/pantry/expiring?within_days=3`),
      ]);
      if (invRes.ok) {
        const inv = await invRes.json();
        setItems(inv.inventory?.items || []);
      }
      if (expRes.ok) {
        const exp = await expRes.json();
        setExpiring(exp.expiring || []);
      }
    } catch {
      setError("Failed to load pantry. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    if (!isAuthenticated) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadAll();
  }, [loadAll, isAuthenticated]);

  function errMsg(err: unknown, fallback: string): string {
    return err instanceof Error && err.message ? err.message : fallback;
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      setError("Enter an ingredient name.");
      return;
    }
    setAction("add");
    setError(null);
    try {
      const res = await authFetch(`${apiBaseUrl}/api/tracker/pantry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          collection: "pantry",
          title: formName.trim(),
          data: {
            quantity: parseFloat(formQty) || 1,
            unit: formUnit,
            category: formCategory,
            ...(formExpiry ? { expiry: formExpiry } : {}),
          },
          user_id: "default_user",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to add item");
      }
      setFormName("");
      setFormQty("1");
      setFormExpiry("");
      setShowAdd(false);
      await loadAll();
    } catch (err) {
      setError(errMsg(err, "Failed to add item."));
    } finally {
      setAction(null);
    }
  };

  const handleConsume = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!consuming) return;
    setAction("consume");
    setError(null);
    try {
      const res = await authFetch(`${apiBaseUrl}/api/tracker/pantry/consume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          data: {
            name: consuming.name,
            quantity: parseFloat(consumeQty) || 1,
          },
          user_id: "default_user",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to consume item");
      }
      setConsuming(null);
      setConsumeQty("1");
      await loadAll();
    } catch (err) {
      setError(errMsg(err, "Failed to consume item."));
    } finally {
      setAction(null);
    }
  };

  const handleDelete = async (item: PantryItem) => {
    if (!item.id) return;
    if (!confirm(`Delete '${item.name}' from the pantry?`)) return;
    setAction(`del-${item.name}`);
    setError(null);
    try {
      const res = await authFetch(`${apiBaseUrl}/api/tracker/records/${item.id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Failed to delete item");
      await loadAll();
    } catch (err) {
      setError(errMsg(err, "Failed to delete item."));
    } finally {
      setAction(null);
    }
  };

  const handlePlan = async () => {
    setPlanning(true);
    setError(null);
    try {
      const res = await authFetch(
        `${apiBaseUrl}/api/tracker/pantry/meal-plan?requested=${mealCount}`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error("Failed to generate meal plan");
      const data = await res.json();
      setPlan(data.plan || null);
    } catch (err) {
      setError(errMsg(err, "Failed to generate meal plan."));
    } finally {
      setPlanning(false);
    }
  };

  const totalItems = items.reduce((sum, i) => sum + (i.quantity || 0), 0);
  const expiringCount = expiring.filter((e) => e.days_to_expiry <= 3).length;

  if (!isAuthenticated) {
    return (
      <ApiKeyGate
        onAuthenticated={() => setIsAuthenticated(true)}
        apiBaseUrl={apiBaseUrl}
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-slate-800/80 bg-slate-900/80 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="p-2 rounded-xl bg-slate-800/70 hover:bg-slate-800 border border-slate-700/40 text-slate-300 transition-colors"
              title="Back to chat"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-gradient-to-tr from-emerald-500 to-teal-500 rounded-xl">
                <Package className="w-5 h-5 text-slate-950" />
              </div>
              <div>
                <h1 className="text-base font-bold tracking-tight text-white">Pantry</h1>
                <p className="text-[10px] text-slate-400 uppercase tracking-wider">Grocery Inventory & Meal Planning</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowAdd((s) => !s)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-all active:scale-95"
            >
              <Plus className="w-3.5 h-3.5" /> {showAdd ? "Cancel" : "Add Item"}
            </button>
            <button
              onClick={loadAll}
              disabled={loading}
              className="p-2 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/40 text-slate-300 transition-colors"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-teal-400" : ""}`} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {error && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            {error}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl">
            <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Ingredients</span>
            <span className="text-lg font-extrabold text-emerald-400">{items.length}</span>
          </div>
          <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl">
            <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Total Qty</span>
            <span className="text-lg font-extrabold text-teal-400">{totalItems.toFixed(1)}</span>
          </div>
          <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl">
            <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Expiring ≤3d</span>
            <span className={`text-lg font-extrabold ${expiringCount > 0 ? "text-amber-400" : "text-slate-300"}`}>
              {expiringCount}
            </span>
          </div>
          <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl">
            <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Meals</span>
            <span className="text-lg font-extrabold text-purple-400">{plan?.meals?.length || 0}</span>
          </div>
        </div>

        {/* Expiry Alert Strip */}
        {expiring.length > 0 && (
          <div className="flex items-start gap-2.5 p-3 rounded-xl bg-amber-500/10 border border-amber-500/30">
            <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
            <div className="text-xs text-amber-200/90">
              <span className="font-bold text-amber-300 block mb-1">Use these up soon:</span>
              <div className="flex flex-wrap gap-1.5">
                {expiring.map((e) => {
                  const tone = expiryTone(e.days_to_expiry);
                  return (
                    <span key={e.name} className={`px-2 py-0.5 rounded-full border text-[10px] font-medium ${tone.badge}`}>
                      {e.name} ({e.quantity} {e.unit})
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Add form */}
        {showAdd && (
          <form onSubmit={handleAdd} className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Ingredient</label>
                <input
                  type="text"
                  placeholder="e.g. tomatoes, chicken breast"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-sm text-white focus:outline-none focus:border-teal-500"
                  required
                />
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Quantity</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formQty}
                  onChange={(e) => setFormQty(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-sm text-white font-mono focus:outline-none focus:border-teal-500"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Unit</label>
                <select
                  value={formUnit}
                  onChange={(e) => setFormUnit(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-sm text-white focus:outline-none focus:border-teal-500"
                >
                  {UNITS.map((u) => (
                    <option key={u} value={u}>{u}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Category</label>
                <select
                  value={formCategory}
                  onChange={(e) => setFormCategory(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-sm text-white focus:outline-none focus:border-teal-500"
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Expiry Date (optional)</label>
                <input
                  type="date"
                  value={formExpiry}
                  onChange={(e) => setFormExpiry(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-sm text-white focus:outline-none focus:border-teal-500"
                />
              </div>
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={action === "add"}
                className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white flex items-center gap-1.5"
              >
                {action === "add" && <RefreshCw className="w-3 h-3 animate-spin" />}
                Add to Pantry
              </button>
            </div>
          </form>
        )}

        {/* Inventory */}
        <section>
          <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-2">
            <Package className="w-3.5 h-3.5 text-emerald-400" /> Inventory
          </h2>
          {loading ? (
            <div className="flex items-center justify-center py-16 text-slate-400">
              <RefreshCw className="w-5 h-5 animate-spin text-teal-400" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-12 border border-dashed border-slate-800 rounded-2xl text-slate-500">
              <Package className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-sm">Your pantry is empty.</p>
              <p className="text-xs text-slate-600 mt-1">Add ingredients above, or just tell Jarvis in chat.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {items.map((item) => {
                const tone = expiryTone(item.days_to_expiry);
                const urgent = item.days_to_expiry !== null && item.days_to_expiry !== undefined && item.days_to_expiry <= 3;
                return (
                  <div
                    key={item.name}
                    className={`p-3.5 bg-slate-900/60 border rounded-xl transition-colors ${
                      urgent ? "border-amber-500/40 bg-amber-500/5" : "border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        {CATEGORY_ICONS[item.category] || CATEGORY_ICONS.other}
                        <h3 className="text-sm font-semibold text-slate-100 truncate capitalize">{item.name}</h3>
                      </div>
                      <button
                        onClick={() => handleDelete(item)}
                        disabled={action === `del-${item.name}`}
                        className="text-slate-500 hover:text-rose-400 p-1 rounded-lg hover:bg-slate-800/60 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-lg font-extrabold font-mono text-white">
                        {item.quantity} <span className="text-xs font-normal text-slate-400">{item.unit}</span>
                      </span>
                      <button
                        onClick={() => { setConsuming(item); setConsumeQty(String(item.quantity || 1)); }}
                        className="flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-[10px] font-semibold text-teal-300 transition-colors"
                      >
                        <Minus className="w-3 h-3" /> Use
                      </button>
                    </div>
                    <div className="mt-2 flex items-center gap-1.5">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${tone.badge}`}>
                        {tone.label}
                      </span>
                      {item.expiry && (
                        <span className="text-[10px] text-slate-500">{item.expiry}</span>
                      )}
                    </div>
                    <span className="mt-1.5 inline-block text-[9px] uppercase tracking-wider text-slate-500">
                      {item.category}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Consume inline */}
        {consuming && (
          <form onSubmit={handleConsume} className="p-4 bg-slate-900/80 border border-teal-500/30 rounded-2xl space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <Utensils className="w-4 h-4 text-teal-400" /> Use <span className="capitalize">{consuming.name}</span>
              </span>
              <button type="button" onClick={() => setConsuming(null)} className="text-slate-400 hover:text-white text-xs">
                Cancel
              </button>
            </div>
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Quantity to consume</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={consumeQty}
                  onChange={(e) => setConsumeQty(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-sm text-white font-mono focus:outline-none focus:border-teal-500"
                />
              </div>
              <button
                type="submit"
                disabled={action === "consume"}
                className="px-4 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-xs font-semibold text-white"
              >
                {action === "consume" ? "..." : "Consume"}
              </button>
            </div>
          </form>
        )}

        {/* Meal Planning */}
        <section>
          <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" /> Meal Planning
          </h2>
          <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-2xl">
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-xs text-slate-400 flex-1 min-w-[200px]">
                Generate cookable meal ideas from what&apos;s actually in your pantry — expiring items get used first.
              </p>
              <select
                value={mealCount}
                onChange={(e) => setMealCount(parseInt(e.target.value))}
                className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-teal-500"
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>{n} meal{n > 1 ? "s" : ""}</option>
                ))}
              </select>
              <button
                onClick={handlePlan}
                disabled={planning || items.length === 0}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-xs font-semibold text-white disabled:opacity-40 transition-all active:scale-95"
              >
                {planning ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                {planning ? "Planning..." : "Generate Meal Plan"}
              </button>
            </div>

            {plan && (
              <div className="mt-4 space-y-3">
                {!plan.generated && plan.note && (
                  <p className="text-xs text-slate-400 italic">{plan.note}</p>
                )}
                {plan.meals.map((meal, idx) => {
                  const missing = meal.missing_ingredients;
                  const fullyCookable = missing.length === 0;
                  return (
                    <div key={idx} className={`p-3.5 rounded-xl border ${
                      meal.uses_expiring ? "border-amber-500/40 bg-amber-500/5" : "border-slate-800 bg-slate-950/50"
                    }`}>
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                            {meal.name}
                            {meal.uses_expiring && (
                              <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold">
                                uses expiring ✓
                              </span>
                            )}
                          </h3>
                          <p className="text-xs text-slate-400 mt-0.5">{meal.summary}</p>
                        </div>
                        <span className={`text-[10px] px-2 py-1 rounded-full border font-semibold flex-shrink-0 ${
                          fullyCookable
                            ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                            : "bg-slate-800 text-amber-300 border-slate-700"
                        }`}>
                          {fullyCookable ? "✓ Cookable" : `${missing.length} to get`}
                        </span>
                      </div>
                      {missing.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {missing.map((m, mi) => (
                            <span
                              key={mi}
                              className={`px-2 py-0.5 rounded-full text-[10px] border ${
                                m.required
                                  ? "bg-rose-500/10 text-rose-300 border-rose-500/30"
                                  : "bg-slate-800 text-slate-400 border-slate-700"
                              }`}
                            >
                              {m.name}{m.quantity ? ` (${m.quantity})` : ""}{!m.required ? " *" : ""}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
