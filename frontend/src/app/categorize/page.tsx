"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken() {
  return document.cookie.split("; ").find(r => r.startsWith("al_token="))?.split("=")[1];
}

async function api(path: string, options: RequestInit = {}) {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  return res.json();
}

type Suggestion = {
  id: string;
  category: string;
  confidence: "high" | "medium" | "low";
  reason: string;
  description: string;
  amount: number;
  type: string;
  date: string;
  approved?: boolean;
  edited?: boolean;
};

const CATEGORIES = [
  "Botox / Neurotoxin", "Dermal Fillers", "Laser Treatment",
  "Skincare / Facials", "Body Contouring", "Chemical Peel",
  "Microneedling", "PRP Treatment", "IV Therapy",
  "Medical Supplies", "Injectable Supplies", "Equipment Maintenance",
  "Staff / Payroll", "Marketing / Advertising", "Rent / Utilities",
  "Insurance", "Software / Technology", "Office Supplies",
  "Professional Development", "Consultation / Service Fee",
  "Retail Products", "Other Income", "Other Expense",
];

const confidenceColor = {
  high: "bg-teal-50 text-teal-700",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-red-50 text-red-600",
};

export default function CategorizePage() {
  const router = useRouter();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uncategorizedCount, setUncategorizedCount] = useState(0);
  const [message, setMessage] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace("/login"); return; }
    setReady(true);
    loadUncategorized();
  }, []);

  async function loadUncategorized() {
    const data = await api("/api/v1/categorize/uncategorized");
    setUncategorizedCount(data.count || 0);
  }

  async function handleSuggest() {
    setLoading(true);
    setMessage("");
    setSuggestions([]);
    try {
      const data = await api("/api/v1/categorize/suggest", { method: "POST" });
      if (data.error) {
        setMessage(`Error: ${data.error}`);
      } else {
        setSuggestions(data.suggestions || []);
        if (data.suggestions?.length === 0) setMessage("No uncategorized transactions found.");
      }
    } catch (e) {
      setMessage("Failed to get suggestions. Check API connection.");
    } finally {
      setLoading(false);
    }
  }

  function updateCategory(id: string, category: string) {
    setSuggestions(prev => prev.map(s =>
      s.id === id ? { ...s, category, edited: true } : s
    ));
  }

  function toggleApprove(id: string) {
    setSuggestions(prev => prev.map(s =>
      s.id === id ? { ...s, approved: !s.approved } : s
    ));
  }

  function approveAll() {
    setSuggestions(prev => prev.map(s => ({ ...s, approved: true })));
  }

  async function saveApproved() {
    const approved = suggestions.filter(s => s.approved);
    if (approved.length === 0) {
      setMessage("No suggestions approved yet. Check the boxes next to each one.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      // Save each approved suggestion
      let saved = 0;
      for (const s of approved) {
        await api("/api/v1/categorize/approve", {
          method: "POST",
          body: JSON.stringify({
            transaction_id: s.id,
            category: s.category,
            write_to_quickbooks: true,
          }),
        });
        saved++;
      }
      setMessage(`✓ ${saved} transactions categorized and synced to QuickBooks`);
      setSuggestions(prev => prev.filter(s => !s.approved));
      await loadUncategorized();
    } catch (e) {
      setMessage("Save failed — try again");
    } finally {
      setSaving(false);
    }
  }

  const approvedCount = suggestions.filter(s => s.approved).length;

  if (!ready) return null;

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <a href="/" className="text-xs uppercase tracking-widest text-teal-700 font-medium">
            Nursify MedSpa AI
          </a>
          <span className="text-gray-300">|</span>
          <span className="text-sm text-gray-600">AI Categorization</span>
        </div>
        <a href="/" className="text-sm text-gray-400 hover:text-gray-600">← Back to dashboard</a>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8 space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-medium text-gray-900">AI Categorization</h1>
            <p className="text-sm text-gray-500 mt-1">
              {uncategorizedCount > 0
                ? `${uncategorizedCount} uncategorized transactions — Claude AI will suggest categories for each one`
                : "All transactions are categorized"}
            </p>
          </div>
          <button onClick={handleSuggest} disabled={loading || uncategorizedCount === 0}
            className="bg-teal-700 hover:bg-teal-800 text-white rounded-lg px-5 py-2.5 text-sm font-medium disabled:opacity-40 transition-colors">
            {loading ? "Analyzing…" : "Get AI suggestions"}
          </button>
        </div>

        {message && (
          <div className={`text-sm rounded-lg px-4 py-3 border ${message.startsWith("✓")
            ? "bg-teal-50 text-teal-700 border-teal-200"
            : "bg-amber-50 text-amber-700 border-amber-200"}`}>
            {message}
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <div className="text-gray-400 text-sm">Claude is analyzing your transactions…</div>
            <div className="mt-3 text-xs text-gray-300">This takes about 5-10 seconds</div>
          </div>
        )}

        {/* Suggestions */}
        {suggestions.length > 0 && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-600">
                {approvedCount} of {suggestions.length} approved
              </p>
              <div className="flex gap-3">
                <button onClick={approveAll}
                  className="text-sm text-teal-700 border border-teal-200 rounded-lg px-3 py-1.5 hover:bg-teal-50">
                  Approve all
                </button>
                <button onClick={saveApproved} disabled={saving || approvedCount === 0}
                  className="bg-teal-700 hover:bg-teal-800 text-white rounded-lg px-4 py-1.5 text-sm disabled:opacity-40">
                  {saving ? "Saving…" : `Save ${approvedCount > 0 ? `(${approvedCount})` : ""} to QuickBooks`}
                </button>
              </div>
            </div>

            <div className="space-y-3">
              {suggestions.map(s => (
                <div key={s.id}
                  className={`bg-white rounded-xl border p-4 transition-all ${s.approved ? "border-teal-300 bg-teal-50/30" : "border-gray-200"}`}>
                  <div className="flex items-start gap-4">

                    {/* Checkbox */}
                    <input type="checkbox" checked={s.approved || false}
                      onChange={() => toggleApprove(s.id)}
                      className="mt-1 w-4 h-4 accent-teal-700 cursor-pointer flex-shrink-0" />

                    {/* Transaction info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="font-medium text-gray-900 truncate">{s.description || "No description"}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${s.type === "revenue" ? "bg-teal-50 text-teal-700" : "bg-gray-100 text-gray-600"}`}>
                          {s.type}
                        </span>
                        <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${confidenceColor[s.confidence]}`}>
                          {s.confidence} confidence
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-gray-500 mb-3">
                        <span className={`font-medium ${s.type === "revenue" ? "text-teal-700" : "text-gray-700"}`}>
                          {s.type === "revenue" ? "+" : "-"}${s.amount.toFixed(2)}
                        </span>
                        <span>{new Date(s.date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
                      </div>
                      <p className="text-xs text-gray-400 mb-3">AI reasoning: {s.reason}</p>

                      {/* Category selector */}
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-gray-500 flex-shrink-0">Category:</span>
                        <select value={s.category} onChange={e => updateCategory(s.id, e.target.value)}
                          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-teal-500 flex-1 max-w-xs">
                          {CATEGORIES.map(c => (
                            <option key={c} value={c}>{c}</option>
                          ))}
                        </select>
                        {s.edited && <span className="text-xs text-amber-600">edited</span>}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {approvedCount > 0 && (
              <div className="flex justify-end pb-8">
                <button onClick={saveApproved} disabled={saving}
                  className="bg-teal-700 hover:bg-teal-800 text-white rounded-lg px-6 py-2.5 text-sm font-medium disabled:opacity-40">
                  {saving ? "Saving to QuickBooks…" : `Save ${approvedCount} categories to QuickBooks`}
                </button>
              </div>
            )}
          </>
        )}

        {/* Empty state */}
        {!loading && suggestions.length === 0 && uncategorizedCount > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <p className="text-gray-500 text-sm mb-2">
              {uncategorizedCount} transactions need categories
            </p>
            <p className="text-gray-400 text-xs">Click "Get AI suggestions" to analyze them</p>
          </div>
        )}

        {uncategorizedCount === 0 && suggestions.length === 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <p className="text-teal-700 font-medium">All transactions are categorized</p>
            <p className="text-gray-400 text-xs mt-1">Sync QuickBooks to check for new ones</p>
          </div>
        )}
      </main>
    </div>
  );
}
