"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  X,
  Plus,
  Trash2,
  CheckCircle2,
  Circle,
  ExternalLink,
  Calendar,
  DollarSign,
  Tag,
  Search,
  Filter,
  RefreshCw,
  TrendingUp,
  Clock,
  Bookmark,
  CheckSquare,
  FileText,
  Layers,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Fuel,
  Gauge,
  Car,
} from "lucide-react";

export interface TrackerItem {
  id: string;
  user_id: string;
  collection: string;
  title: string;
  data: Record<string, any>;
  event_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface CollectionSummary {
  collection: string;
  count: number;
  latest_created_at: string | null;
}

export interface GasAnalytics {
  total_spent: number;
  total_gallons: number;
  avg_price_per_gallon: number;
  fill_count: number;
  latest_odometer: number | null;
  avg_mpg: number | null;
  station_breakdown: Record<string, { spent: number; count: number; gallons: number }>;
}

interface TrackerModalProps {
  isOpen: boolean;
  onClose: () => void;
  apiBaseUrl?: string;
}

export default function TrackerModal({
  isOpen,
  onClose,
  apiBaseUrl = "http://localhost:8000"
}: TrackerModalProps) {
  const [records, setRecords] = useState<TrackerItem[]>([]);
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [dateFilter, setDateFilter] = useState<"all" | "today" | "week" | "month">("all");
  const [loading, setLoading] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState<boolean>(false);
  const [expandedRecordId, setExpandedRecordId] = useState<string | null>(null);

  // Analytics summary state
  const [totalSpent, setTotalSpent] = useState<number>(0);
  const [expenseBreakdown, setExpenseBreakdown] = useState<Record<string, { value: number; count: number }>>({});
  const [pendingTasksCount, setPendingTasksCount] = useState<number>(0);
  const [completedTasksCount, setCompletedTasksCount] = useState<number>(0);
  const [upcomingRemindersCount, setUpcomingRemindersCount] = useState<number>(0);
  const [gasAnalytics, setGasAnalytics] = useState<GasAnalytics | null>(null);

  // Add item form state
  const [formCollection, setFormCollection] = useState<string>("expense");
  const [formTitle, setFormTitle] = useState<string>("");
  const [formEventDate, setFormEventDate] = useState<string>("");
  const [formAmount, setFormAmount] = useState<string>("");
  const [formCategory, setFormCategory] = useState<string>("general");
  const [formCurrency, setFormCurrency] = useState<string>("USD");
  const [formPriority, setFormPriority] = useState<string>("medium");
  const [formUrl, setFormUrl] = useState<string>("");
  const [formTags, setFormTags] = useState<string>("");
  const [formNotes, setFormNotes] = useState<string>("");
  const [formGallons, setFormGallons] = useState<string>("");
  const [formPricePerGallon, setFormPricePerGallon] = useState<string>("");
  const [formOdometer, setFormOdometer] = useState<string>("");
  const [formStation, setFormStation] = useState<string>("");
  const [formVehicle, setFormVehicle] = useState<string>("");
  const [formFuelGrade, setFormFuelGrade] = useState<string>("Regular 87");
  const [formError, setFormError] = useState<string | null>(null);

  const getDateBounds = (filter: "all" | "today" | "week" | "month") => {
    if (filter === "all") return {};
    const now = new Date();
    let from = new Date();
    if (filter === "today") {
      from.setHours(0, 0, 0, 0);
    } else if (filter === "week") {
      from.setDate(now.getDate() - 7);
    } else if (filter === "month") {
      from.setDate(now.getDate() - 30);
    }
    return {
      date_from: from.toISOString().split("T")[0],
    };
  };

  const fetchCollections = useCallback(async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/tracker/collections`);
      if (res.ok) {
        const data = await res.json();
        setCollections(data.collections || []);
      }
    } catch (err) {
      console.error("Failed to fetch collections summary:", err);
    }
  }, [apiBaseUrl]);

  const fetchAnalytics = useCallback(async () => {
    try {
      // 1. Fetch expense aggregation
      const expenseRes = await fetch(
        `${apiBaseUrl}/api/tracker/aggregate?collection=expense&calculation=sum&field=amount&group_by=category`
      );
      if (expenseRes.ok) {
        const expData = await expenseRes.json();
        if (expData.analytics) {
          setTotalSpent(expData.analytics.result || 0);
          setExpenseBreakdown(expData.analytics.breakdown || {});
        }
      }

      // 2. Fetch todo aggregation
      const todoPendingRes = await fetch(
        `${apiBaseUrl}/api/tracker/records?collection=todo&limit=200`
      );
      if (todoPendingRes.ok) {
        const todoData = await todoPendingRes.json();
        const items = todoData.records || [];
        const pending = items.filter((i: TrackerItem) => i.data?.status !== "completed").length;
        const completed = items.filter((i: TrackerItem) => i.data?.status === "completed").length;
        setPendingTasksCount(pending);
        setCompletedTasksCount(completed);
      }

      // 3. Fetch reminders count
      const reminderRes = await fetch(
        `${apiBaseUrl}/api/tracker/records?collection=reminder&limit=200`
      );
      if (reminderRes.ok) {
        const remData = await reminderRes.json();
        const items = remData.records || [];
        const upcoming = items.filter((i: TrackerItem) => i.data?.status !== "sent").length;
        setUpcomingRemindersCount(upcoming);
      }

      // 4. Fetch gas analytics
      const gasRes = await fetch(`${apiBaseUrl}/api/tracker/gas-analytics`);
      if (gasRes.ok) {
        const gasData = await gasRes.json();
        setGasAnalytics(gasData.analytics || null);
      }
    } catch (err) {
      console.error("Failed to fetch analytics:", err);
    }
  }, [apiBaseUrl]);

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    try {
      const { date_from } = getDateBounds(dateFilter);
      let url = `${apiBaseUrl}/api/tracker/records?limit=100`;
      if (selectedCollection !== "all") {
        url += `&collection=${encodeURIComponent(selectedCollection)}`;
      }
      if (searchQuery.trim()) {
        url += `&search=${encodeURIComponent(searchQuery.trim())}`;
      }
      if (date_from) {
        url += `&date_from=${encodeURIComponent(date_from)}`;
      }

      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setRecords(data.records || []);
      }
    } catch (err) {
      console.error("Failed to fetch tracker records:", err);
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, selectedCollection, searchQuery, dateFilter]);

  useEffect(() => {
    if (isOpen) {
      fetchCollections();
      fetchAnalytics();
      fetchRecords();
    }
  }, [isOpen, fetchCollections, fetchAnalytics, fetchRecords]);

  const handleCreateRecord = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTitle.trim()) {
      setFormError("Title is required");
      return;
    }

    setFormError(null);
    setActionLoading("creating");

    try {
      const data: Record<string, any> = {};

      if (formCollection === "gas") {
        const amt = parseFloat(formAmount) || 0;
        const gals = parseFloat(formGallons) || 0;
        const ppg = parseFloat(formPricePerGallon) || (amt > 0 && gals > 0 ? +(amt / gals).toFixed(3) : 0);
        data.amount = amt;
        data.gallons = gals;
        data.price_per_gallon = ppg;
        data.currency = formCurrency.trim() || "USD";
        if (formOdometer) data.odometer = parseFloat(formOdometer);
        if (formStation.trim()) data.station = formStation.trim();
        if (formVehicle.trim()) data.vehicle = formVehicle.trim();
        if (formFuelGrade.trim()) data.fuel_grade = formFuelGrade.trim();
      } else if (formCollection === "expense") {
        data.amount = parseFloat(formAmount) || 0;
        data.category = formCategory.trim() || "general";
        data.currency = formCurrency.trim() || "USD";
      } else if (formCollection === "todo") {
        data.priority = formPriority;
        data.status = "pending";
      } else if (formCollection === "bookmark") {
        data.url = formUrl.trim();
        data.tags = formTags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean);
      } else if (formCollection === "reminder") {
        data.status = "scheduled";
        if (formNotes.trim()) data.notes = formNotes.trim();
      }

      if (formNotes.trim() && formCollection !== "reminder") {
        data.notes = formNotes.trim();
      }

      const payload = {
        collection: formCollection.toLowerCase().trim(),
        title: formTitle.trim(),
        data,
        event_date: formEventDate ? new Date(formEventDate).toISOString() : null,
        user_id: "default_user",
      };

      const res = await fetch(`${apiBaseUrl}/api/tracker/records`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to create record");
      }

      // Reset form
      setFormTitle("");
      setFormAmount("");
      setFormUrl("");
      setFormTags("");
      setFormNotes("");
      setFormGallons("");
      setFormPricePerGallon("");
      setFormOdometer("");
      setFormStation("");
      setFormVehicle("");
      setFormFuelGrade("Regular 87");
      setFormEventDate("");
      setShowAddForm(false);

      // Refresh records
      await Promise.all([fetchRecords(), fetchCollections(), fetchAnalytics()]);
    } catch (err: any) {
      setFormError(err.message || "Failed to save record");
    } finally {
      setActionLoading(null);
    }
  };

  const handleToggleTodoStatus = async (item: TrackerItem) => {
    setActionLoading(item.id);
    const newStatus = item.data?.status === "completed" ? "pending" : "completed";
    try {
      const res = await fetch(`${apiBaseUrl}/api/tracker/records/${item.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: newStatus,
          data: { ...item.data, status: newStatus },
        }),
      });
      if (res.ok) {
        setRecords((prev) =>
          prev.map((r) => (r.id === item.id ? { ...r, data: { ...r.data, status: newStatus } } : r))
        );
        fetchAnalytics();
      }
    } catch (err) {
      console.error("Failed to toggle todo status:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteRecord = async (id: string) => {
    if (!confirm("Are you sure you want to delete this item?")) return;
    setActionLoading(id);
    try {
      const res = await fetch(`${apiBaseUrl}/api/tracker/records/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setRecords((prev) => prev.filter((r) => r.id !== id));
        fetchCollections();
        fetchAnalytics();
      }
    } catch (err) {
      console.error("Failed to delete record:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const getCollectionBadge = (coll: string) => {
    switch (coll.toLowerCase()) {
      case "gas":
      case "fuel":
        return "bg-amber-500/10 text-amber-300 border-amber-500/30";
      case "expense":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "todo":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      case "reminder":
        return "bg-purple-500/10 text-purple-400 border-purple-500/20";
      case "bookmark":
        return "bg-cyan-500/10 text-cyan-400 border-cyan-500/20";
      case "note":
        return "bg-blue-500/10 text-blue-400 border-blue-500/20";
      default:
        return "bg-slate-700/30 text-slate-300 border-slate-700/40";
    }
  };

  const getCollectionIcon = (coll: string) => {
    switch (coll.toLowerCase()) {
      case "gas":
      case "fuel":
        return <Fuel className="w-3.5 h-3.5 text-amber-400" />;
      case "expense":
        return <DollarSign className="w-3.5 h-3.5 text-emerald-400" />;
      case "todo":
        return <CheckSquare className="w-3.5 h-3.5 text-amber-400" />;
      case "reminder":
        return <Clock className="w-3.5 h-3.5 text-purple-400" />;
      case "bookmark":
        return <Bookmark className="w-3.5 h-3.5 text-cyan-400" />;
      default:
        return <FileText className="w-3.5 h-3.5 text-blue-400" />;
    }
  };

  if (!isOpen) return null;

  const isGasCollectionSelected = selectedCollection.toLowerCase() === "gas" || selectedCollection.toLowerCase() === "fuel";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 w-full max-w-5xl h-[88vh] rounded-2xl shadow-2xl flex flex-col overflow-hidden text-slate-100 font-sans">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-tr from-emerald-500 to-teal-500 rounded-xl shadow-lg shadow-emerald-500/10">
              <Layers className="w-5 h-5 text-slate-950" />
            </div>
            <div>
              <h2 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
                Tracker & Second Brain
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                  Universal JSONB Store
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Log and query gas fill-ups, expenses, to-dos, reminders, and bookmarks in one place.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                fetchRecords();
                fetchCollections();
                fetchAnalytics();
              }}
              disabled={loading}
              className="p-2 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/40 text-slate-300 transition-colors"
              title="Refresh Records"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-teal-400" : ""}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/40 text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Analytics KPI Ribbon */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 px-6 py-3 bg-slate-950/40 border-b border-slate-800/60">
          {isGasCollectionSelected ? (
            <>
              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Total Fuel Spend</span>
                  <span className="text-lg font-extrabold text-amber-400 font-mono">
                    ${(gasAnalytics?.total_spent || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="p-2 bg-amber-500/10 rounded-lg text-amber-400">
                  <Fuel className="w-4 h-4" />
                </div>
              </div>

              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Total Gallons</span>
                  <span className="text-lg font-extrabold text-teal-400 font-mono">
                    {(gasAnalytics?.total_gallons || 0).toFixed(1)} <span className="text-xs text-slate-500 font-normal">gal</span>
                  </span>
                </div>
                <div className="p-2 bg-teal-500/10 rounded-lg text-teal-400">
                  <Gauge className="w-4 h-4" />
                </div>
              </div>

              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Avg Price / Gal</span>
                  <span className="text-lg font-extrabold text-emerald-400 font-mono">
                    ${(gasAnalytics?.avg_price_per_gallon || 0).toFixed(2)}
                  </span>
                </div>
                <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
                  <DollarSign className="w-4 h-4" />
                </div>
              </div>

              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Avg MPG / Odometer</span>
                  <span className="text-sm font-bold text-slate-200 block font-mono">
                    {gasAnalytics?.avg_mpg ? `${gasAnalytics.avg_mpg} MPG` : gasAnalytics?.latest_odometer ? `${gasAnalytics.latest_odometer.toLocaleString()} mi` : "N/A"}
                  </span>
                </div>
                <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
                  <Car className="w-4 h-4" />
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Total Spent</span>
                  <span className="text-lg font-extrabold text-emerald-400 font-mono">
                    ${totalSpent.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
                  <DollarSign className="w-4 h-4" />
                </div>
              </div>

              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Pending Tasks</span>
                  <span className="text-lg font-extrabold text-amber-400 font-mono">
                    {pendingTasksCount} <span className="text-xs text-slate-500 font-normal">({completedTasksCount} done)</span>
                  </span>
                </div>
                <div className="p-2 bg-amber-500/10 rounded-lg text-amber-400">
                  <CheckSquare className="w-4 h-4" />
                </div>
              </div>

              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Active Reminders</span>
                  <span className="text-lg font-extrabold text-purple-400 font-mono">
                    {upcomingRemindersCount}
                  </span>
                </div>
                <div className="p-2 bg-purple-500/10 rounded-lg text-purple-400">
                  <Clock className="w-4 h-4" />
                </div>
              </div>

              <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">Top Category</span>
                  <span className="text-sm font-bold text-slate-200 truncate max-w-[110px] block">
                    {Object.keys(expenseBreakdown)[0] || "N/A"}
                  </span>
                </div>
                <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
                  <TrendingUp className="w-4 h-4" />
                </div>
              </div>
            </>
          )}
        </div>

        {/* Action & Filter Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-3 border-b border-slate-800/60 bg-slate-900/40">
          
          {/* Collection Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-1">
            <button
              onClick={() => setSelectedCollection("all")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                selectedCollection === "all"
                  ? "bg-teal-500 text-slate-950 shadow-md shadow-teal-500/20"
                  : "bg-slate-800/60 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              All Items ({records.length})
            </button>
            {collections.map((c) => (
              <button
                key={c.collection}
                onClick={() => setSelectedCollection(c.collection)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all flex items-center gap-1.5 ${
                  selectedCollection === c.collection
                    ? "bg-teal-500 text-slate-950 shadow-md shadow-teal-500/20"
                    : "bg-slate-800/60 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                }`}
              >
                {getCollectionIcon(c.collection)}
                <span>{c.collection}</span>
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                  selectedCollection === c.collection ? "bg-slate-950/30 text-slate-950" : "bg-slate-700/50 text-slate-300"
                }`}>
                  {c.count}
                </span>
              </button>
            ))}
          </div>

          {/* Search, Date Filter & Add Button */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search items..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 bg-slate-950/60 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-teal-500 w-44"
              />
            </div>

            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value as any)}
              className="bg-slate-950/60 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-teal-500"
            >
              <option value="all">All Dates</option>
              <option value="today">Today</option>
              <option value="week">Past 7 Days</option>
              <option value="month">Past 30 Days</option>
            </select>

            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition-all shadow-md shadow-emerald-600/20 active:scale-95"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>{showAddForm ? "Cancel" : "Add Item"}</span>
            </button>
          </div>
        </div>

        {/* Inline Add Item Drawer/Form */}
        {showAddForm && (
          <form onSubmit={handleCreateRecord} className="p-4 bg-slate-950/80 border-b border-slate-800 space-y-3 animate-in slide-in-from-top-2 duration-150">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-200 flex items-center gap-2">
                <Plus className="w-3.5 h-3.5 text-emerald-400" />
                Add New Tracked Entry
              </span>
              {formError && (
                <span className="text-xs text-rose-400 flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" /> {formError}
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Collection</label>
                <select
                  value={formCollection}
                  onChange={(e) => setFormCollection(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white"
                >
                  <option value="gas">Gas / Fuel ⛽</option>
                  <option value="expense">Expense 💰</option>
                  <option value="todo">To-Do Item 📝</option>
                  <option value="reminder">Reminder ⏰</option>
                  <option value="bookmark">Bookmark 🔖</option>
                  <option value="note">Note 💡</option>
                </select>
              </div>

              <div className="md:col-span-2">
                <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Title / Summary</label>
                <input
                  type="text"
                  placeholder="e.g. Fill-up at Costco, Dinner with team, Finish auth API"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-teal-500"
                  required
                />
              </div>

              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Date / Deadline</label>
                <input
                  type="datetime-local"
                  value={formEventDate}
                  onChange={(e) => setFormEventDate(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white"
                />
              </div>
            </div>

            {/* Dynamic fields by collection */}
            {formCollection === "gas" && (
              <div className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Total Cost ($)</label>
                    <input
                      type="number"
                      step="0.01"
                      placeholder="45.00"
                      value={formAmount}
                      onChange={(e) => {
                        const val = e.target.value;
                        setFormAmount(val);
                        if (val && formGallons && parseFloat(formGallons) > 0) {
                          setFormPricePerGallon((parseFloat(val) / parseFloat(formGallons)).toFixed(3));
                        }
                      }}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-amber-400 font-mono font-bold"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Gallons Pumped</label>
                    <input
                      type="number"
                      step="0.001"
                      placeholder="12.5"
                      value={formGallons}
                      onChange={(e) => {
                        const val = e.target.value;
                        setFormGallons(val);
                        if (formAmount && val && parseFloat(val) > 0) {
                          setFormPricePerGallon((parseFloat(formAmount) / parseFloat(val)).toFixed(3));
                        }
                      }}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Price / Gal ($)</label>
                    <input
                      type="number"
                      step="0.001"
                      placeholder="3.60"
                      value={formPricePerGallon}
                      onChange={(e) => setFormPricePerGallon(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 font-mono"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                  <div>
                    <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Odometer (miles)</label>
                    <input
                      type="number"
                      placeholder="54200"
                      value={formOdometer}
                      onChange={(e) => setFormOdometer(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Station / Brand</label>
                    <input
                      type="text"
                      placeholder="Costco, Shell, Exxon"
                      value={formStation}
                      onChange={(e) => setFormStation(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Vehicle</label>
                    <input
                      type="text"
                      placeholder="Civic, RAV4, Model 3"
                      value={formVehicle}
                      onChange={(e) => setFormVehicle(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Fuel Grade</label>
                    <select
                      value={formFuelGrade}
                      onChange={(e) => setFormFuelGrade(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white"
                    >
                      <option value="Regular 87">Regular 87</option>
                      <option value="Midgrade 89">Midgrade 89</option>
                      <option value="Premium 93">Premium 93</option>
                      <option value="Diesel">Diesel</option>
                      <option value="E85">E85</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {formCollection === "expense" && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Amount ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={formAmount}
                    onChange={(e) => setFormAmount(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-emerald-400 font-mono font-bold"
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Category</label>
                  <input
                    type="text"
                    placeholder="food, transport, utilities, travel"
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white"
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Currency</label>
                  <input
                    type="text"
                    value={formCurrency}
                    onChange={(e) => setFormCurrency(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white uppercase"
                  />
                </div>
              </div>
            )}

            {formCollection === "todo" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Priority</label>
                  <select
                    value={formPriority}
                    onChange={(e) => setFormPriority(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white"
                  >
                    <option value="low">Low Priority</option>
                    <option value="medium">Medium Priority</option>
                    <option value="high">High Priority 🚨</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Notes (Optional)</label>
                  <input
                    type="text"
                    placeholder="Additional context or checklist details"
                    value={formNotes}
                    onChange={(e) => setFormNotes(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white"
                  />
                </div>
              </div>
            )}

            {formCollection === "bookmark" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">URL</label>
                  <input
                    type="url"
                    placeholder="https://..."
                    value={formUrl}
                    onChange={(e) => setFormUrl(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-cyan-400"
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Tags (Comma-separated)</label>
                  <input
                    type="text"
                    placeholder="ai, langchain, research, tech"
                    value={formTags}
                    onChange={(e) => setFormTags(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white"
                  />
                </div>
              </div>
            )}

            {formCollection === "reminder" && (
              <div>
                <label className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Reminder Details / Message</label>
                <input
                  type="text"
                  placeholder="e.g. Bring passport and printed tickets"
                  value={formNotes}
                  onChange={(e) => setFormNotes(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white"
                />
              </div>
            )}

            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={actionLoading === "creating"}
                className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white flex items-center gap-1.5 shadow-md shadow-emerald-600/20"
              >
                {actionLoading === "creating" && <RefreshCw className="w-3 h-3 animate-spin" />}
                <span>Save to Database</span>
              </button>
            </div>
          </form>
        )}

        {/* Records Content Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3 scrollbar-thin">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-48 gap-3 text-slate-400">
              <RefreshCw className="w-6 h-6 animate-spin text-teal-400" />
              <span className="text-xs">Loading database records...</span>
            </div>
          ) : records.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-56 gap-3 text-slate-500 border border-dashed border-slate-800/80 rounded-2xl bg-slate-950/20">
              <Layers className="w-8 h-8 text-slate-600" />
              <div className="text-center">
                <p className="text-sm font-semibold text-slate-400">No records found</p>
                <p className="text-xs text-slate-600 mt-1">
                  Ask J.A.R.V.I.S. to track something or click &apos;Add Item&apos; above.
                </p>
              </div>
            </div>
          ) : (
            records.map((item) => {
              const isGas = item.collection.toLowerCase() === "gas" || item.collection.toLowerCase() === "fuel";
              const isExpense = item.collection.toLowerCase() === "expense";
              const isTodo = item.collection.toLowerCase() === "todo";
              const isReminder = item.collection.toLowerCase() === "reminder";
              const isBookmark = item.collection.toLowerCase() === "bookmark";
              const isCompleted = isTodo && item.data?.status === "completed";
              const isExpanded = expandedRecordId === item.id;

              return (
                <div
                  key={item.id}
                  className={`p-4 bg-slate-950/50 border border-slate-800/60 hover:border-slate-700/80 rounded-xl transition-all ${
                    isCompleted ? "opacity-60 bg-slate-950/30" : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      {/* Interactive checkbox for todos */}
                      {isTodo && (
                        <button
                          onClick={() => handleToggleTodoStatus(item)}
                          disabled={actionLoading === item.id}
                          className="mt-0.5 text-slate-400 hover:text-emerald-400 transition-colors flex-shrink-0"
                          title={isCompleted ? "Mark incomplete" : "Mark completed"}
                        >
                          {isCompleted ? (
                            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                          ) : (
                            <Circle className="w-5 h-5 text-slate-500" />
                          )}
                        </button>
                      )}

                      <div className="space-y-1 flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${getCollectionBadge(item.collection)}`}>
                            {item.collection}
                          </span>

                          {/* Gas Specific Badges */}
                          {isGas && (
                            <>
                              {item.data?.amount !== undefined && (
                                <span className="text-xs font-extrabold font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-lg border border-amber-500/20">
                                  ${parseFloat(item.data.amount).toFixed(2)}
                                </span>
                              )}
                              {item.data?.gallons !== undefined && (
                                <span className="text-[10px] font-mono text-teal-300 bg-teal-500/10 px-2 py-0.5 rounded-full border border-teal-500/20 flex items-center gap-1">
                                  <Fuel className="w-2.5 h-2.5 text-teal-400" />
                                  {item.data.gallons} gal
                                </span>
                              )}
                              {item.data?.price_per_gallon !== undefined && (
                                <span className="text-[10px] font-mono text-slate-300 bg-slate-800/80 px-2 py-0.5 rounded-full border border-slate-700/60">
                                  ${parseFloat(item.data.price_per_gallon).toFixed(2)}/gal
                                </span>
                              )}
                              {item.data?.odometer !== undefined && (
                                <span className="text-[10px] font-mono text-cyan-300 bg-cyan-500/10 px-2 py-0.5 rounded-full border border-cyan-500/20 flex items-center gap-1">
                                  <Gauge className="w-2.5 h-2.5 text-cyan-400" />
                                  {Number(item.data.odometer).toLocaleString()} mi
                                </span>
                              )}
                              {item.data?.station && (
                                <span className="text-[10px] text-slate-300 bg-slate-800/80 px-2 py-0.5 rounded-full border border-slate-700/60 flex items-center gap-1">
                                  <Tag className="w-2.5 h-2.5 text-amber-400" />
                                  {item.data.station}
                                </span>
                              )}
                              {item.data?.vehicle && (
                                <span className="text-[10px] text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded-full border border-slate-700/60 flex items-center gap-1">
                                  <Car className="w-2.5 h-2.5 text-blue-400" />
                                  {item.data.vehicle}
                                </span>
                              )}
                              {item.data?.fuel_grade && (
                                <span className="text-[10px] text-slate-400 bg-slate-800/60 px-1.5 py-0.2 rounded border border-slate-700/40">
                                  {item.data.fuel_grade}
                                </span>
                              )}
                            </>
                          )}

                          {isExpense && item.data?.amount !== undefined && (
                            <span className="text-xs font-extrabold font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-lg border border-emerald-500/20">
                              ${parseFloat(item.data.amount).toFixed(2)} {item.data.currency || "USD"}
                            </span>
                          )}

                          {item.data?.category && !isGas && (
                            <span className="text-[10px] text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded-full border border-slate-700/60 flex items-center gap-1">
                              <Tag className="w-2.5 h-2.5 text-slate-500" />
                              {item.data.category}
                            </span>
                          )}

                          {item.data?.priority && (
                            <span className={`text-[10px] px-1.5 py-0.2 rounded font-semibold ${
                              item.data.priority === "high"
                                ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                : "bg-slate-800 text-slate-400"
                            }`}>
                              {item.data.priority.toUpperCase()}
                            </span>
                          )}

                          {isReminder && (
                            <span className={`text-[10px] px-2 py-0.5 rounded-full border ${
                              item.data?.status === "sent"
                                ? "bg-slate-800 text-slate-400 border-slate-700"
                                : "bg-purple-500/10 text-purple-300 border-purple-500/30"
                            }`}>
                              {item.data?.status === "sent" ? "Dispatched ✓" : "Scheduled ⏰"}
                            </span>
                          )}
                        </div>

                        {/* Title */}
                        <h4 className={`text-sm font-semibold text-slate-100 break-words ${isCompleted ? "line-through text-slate-400" : ""}`}>
                          {item.title}
                        </h4>

                        {/* Metadata row */}
                        <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-400 pt-0.5">
                          {item.event_date && (
                            <span className="flex items-center gap-1 text-slate-400">
                              <Calendar className="w-3 h-3 text-slate-500" />
                              {new Date(item.event_date).toLocaleString(undefined, {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                          )}

                          {isBookmark && item.data?.url && (
                            <a
                              href={item.data.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1 underline underline-offset-2 truncate max-w-xs"
                            >
                              <ExternalLink className="w-3 h-3 flex-shrink-0" />
                              <span className="truncate">{item.data.url}</span>
                            </a>
                          )}

                          {item.data?.notes && (
                            <span className="text-slate-400 italic">
                              &ldquo;{item.data.notes}&rdquo;
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setExpandedRecordId(isExpanded ? null : item.id)}
                        className="p-1.5 text-slate-500 hover:text-slate-300 rounded-lg hover:bg-slate-900 transition-colors"
                        title="Toggle JSON details"
                      >
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>
                      <button
                        onClick={() => handleDeleteRecord(item.id)}
                        disabled={actionLoading === item.id}
                        className="p-1.5 text-slate-500 hover:text-rose-400 rounded-lg hover:bg-slate-900 transition-colors"
                        title="Delete Record"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Raw JSON detail view */}
                  {isExpanded && (
                    <div className="mt-3 p-2.5 bg-slate-950 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-400 overflow-x-auto">
                      <pre>{JSON.stringify(item.data, null, 2)}</pre>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-950/60 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <span>Total Records Loaded: <strong className="text-slate-200">{records.length}</strong></span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold rounded-xl transition-colors"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
}
