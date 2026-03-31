"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import {
  isLoggedIn, logout, getLast30Days,
  getTransactions, getQBStatus, triggerSync,
} from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function fmt(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}
function fmtFull(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}
function toISO(d: Date) {
  return d.toISOString().split("T")[0];
}

export default function Dashboard() {
  const router = useRouter();
  const [summary, setSummary] = useState<any>(null);
  const [chart, setChart] = useState<any[]>([]);
  const [txns, setTxns] = useState<any[]>([]);
  const [qbStatus, setQbStatus] = useState<any>(null);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState("");
  const [token, setToken] = useState<string | null>(null);

  // Date range state
  const presets = ["Today", "7 days", "30 days", "90 days", "1 year", "All time", "Custom"];
  const [preset, setPreset] = useState("30 days");
  const [startDate, setStartDate] = useState(toISO(new Date(Date.now() - 30 * 86400000)));
  const [endDate, setEndDate] = useState(toISO(new Date()));
  const [showCustom, setShowCustom] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace("/login"); return; }
    const t = document.cookie.split("; ").find(r => r.startsWith("al_token="))?.split("=")[1];
    setToken(t || null);
  }, []);

  useEffect(() => {
    if (token !== null) loadAll();
  }, [token, startDate, endDate]);

  function applyPreset(p: string) {
    setPreset(p);
    setShowCustom(p === "Custom");
    const now = new Date();
    const end = toISO(now);
    const map: Record<string, string> = {
      "Today": toISO(now),
      "7 days": toISO(new Date(now.getTime() - 7 * 86400000)),
      "30 days": toISO(new Date(now.getTime() - 30 * 86400000)),
      "90 days": toISO(new Date(now.getTime() - 90 * 86400000)),
      "1 year": toISO(new Date(now.getTime() - 365 * 86400000)),
      "All time": "2000-01-01",
    };
    if (p !== "Custom") {
      setStartDate(map[p]);
      setEndDate(end);
    }
  }

  async function loadAll() {
    try {
      const [tx, qb] = await Promise.all([
        getTransactions({ start_date: startDate, end_date: endDate, limit: "500" }),
        getQBStatus(),
      ]);
      setTxns(tx.transactions || []);
      setQbStatus(qb);
      buildSummary(tx.transactions || []);
      buildChart(tx.transactions || []);
    } catch (e) {
      console.error(e);
    }
  }

  function buildSummary(txList: any[]) {
    const revenue = txList.filter(t => t.type === "revenue").reduce((s, t) => s + t.amount, 0);
    const expenses = txList.filter(t => t.type === "expense").reduce((s, t) => s + t.amount, 0);
    const fees = txList.filter(t => t.type === "fee").reduce((s, t) => s + t.amount, 0);
    const categories: Record<string, number> = {};
    txList.filter(t => t.type === "revenue").forEach(t => {
      const c = t.category || "uncategorized";
      categories[c] = (categories[c] || 0) + t.amount;
    });
    setSummary({ revenue, expenses, fees, net: revenue - expenses - fees, categories, count: txList.length });
  }

  function buildChart(txList: any[]) {
    const byDate: Record<string, number> = {};
    txList.forEach(t => {
      const d = t.date.split("T")[0];
      if (t.type === "revenue") byDate[d] = (byDate[d] || 0) + t.amount;
    });
    const sorted = Object.entries(byDate).sort(([a], [b]) => a.localeCompare(b));
    setChart(sorted.map(([date, total_revenue]) => ({ date, total_revenue })));
  }

  async function handleSync() {
    setSyncing(true);
    setMessage("");
    try {
      await triggerSync();
      await loadAll();
      setMessage("Sync complete");
    } catch {
      setMessage("Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  async function handleEmail() {
    try {
      const res = await fetch(`${API_URL}/api/v1/reports/generate?send_email=true`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setMessage("Report emailed");
      else setMessage("Email failed — check SMTP settings");
    } catch {
      setMessage("Email failed");
    }
  }

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <span className="text-xs uppercase tracking-widest text-teal-700 font-medium">Nursify MedSpa AI</span>
        <div className="flex items-center gap-3">
          {qbStatus && (
            <span className={`text-xs px-2 py-1 rounded-full ${qbStatus.connected ? "bg-teal-50 text-teal-700" : "bg-red-50 text-red-600"}`}>
              QB {qbStatus.connected ? "connected" : "disconnected"}
            </span>
          )}
          <button onClick={handleSync} disabled={syncing}
            className="text-sm text-gray-600 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50 disabled:opacity-40">
            {syncing ? "Syncing…" : "Sync now"}
          </button>
          <button onClick={logout} className="text-sm text-gray-400 hover:text-gray-600">Sign out</button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {message && (
          <div className="text-sm text-teal-700 bg-teal-50 border border-teal-200 rounded-lg px-4 py-2">{message}</div>
        )}

        {/* Date range selector */}
        <div className="flex items-center gap-2 flex-wrap">
          {presets.map(p => (
            <button key={p} onClick={() => applyPreset(p)}
              className={`text-sm px-3 py-1.5 rounded-lg border transition-colors ${preset === p ? "bg-teal-700 text-white border-teal-700" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
              {p}
            </button>
          ))}
          {showCustom && (
            <div className="flex items-center gap-2 ml-2">
              <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
                className="text-sm border border-gray-200 rounded-lg px-2 py-1.5" />
              <span className="text-gray-400 text-sm">to</span>
              <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
                className="text-sm border border-gray-200 rounded-lg px-2 py-1.5" />
            </div>
          )}
        </div>

        {/* Summary cards */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium">
              {startDate === endDate ? startDate : `${startDate} — ${endDate}`}
            </h2>
            <button onClick={handleEmail}
              className="text-sm text-teal-700 border border-teal-200 rounded-lg px-3 py-1.5 hover:bg-teal-50">
              Send report email
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Revenue", value: summary?.revenue ?? 0, color: "text-teal-700" },
              { label: "Expenses", value: summary?.expenses ?? 0, color: "text-gray-700" },
              { label: "Fees", value: summary?.fees ?? 0, color: "text-gray-700" },
              { label: "Net income", value: summary?.net ?? 0, color: (summary?.net ?? 0) >= 0 ? "text-teal-700" : "text-red-600" },
            ].map(card => (
              <div key={card.label} className="bg-white rounded-xl border border-gray-200 p-4">
                <p className="text-xs text-gray-500 mb-1">{card.label}</p>
                <p className={`text-2xl font-medium ${card.color}`}>{fmt(card.value)}</p>
              </div>
            ))}
          </div>
          {summary && <p className="text-xs text-gray-400 mt-2">{summary.count} transactions</p>}
        </section>

        {/* Chart */}
        {chart.length > 0 && (
          <section>
            <h2 className="text-lg font-medium mb-4">Revenue over time</h2>
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chart} barSize={Math.max(4, Math.min(32, 600 / chart.length))}>
                  <XAxis dataKey="date"
                    tickFormatter={d => new Date(d + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                    tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false}
                    interval={Math.floor(chart.length / 8)} />
                  <YAxis tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
                    tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} width={48} />
                  <Tooltip
                    formatter={(v: number) => [fmtFull(v), "Revenue"]}
                    labelFormatter={d => new Date(d + "T00:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" })}
                    contentStyle={{ border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 13 }} />
                  <Bar dataKey="total_revenue" radius={[3, 3, 0, 0]}>
                    {chart.map((_, i) => <Cell key={i} fill={i === chart.length - 1 ? "#0f6e56" : "#9fe1cb"} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {/* Category breakdown */}
        {summary?.categories && Object.keys(summary.categories).length > 0 && (
          <section>
            <h2 className="text-lg font-medium mb-4">Revenue by service</h2>
            <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
              {Object.entries(summary.categories as Record<string, number>)
                .sort(([, a], [, b]) => b - a)
                .map(([cat, amt]) => (
                  <div key={cat} className="flex items-center justify-between px-5 py-3">
                    <span className="text-sm text-gray-700 capitalize">{cat}</span>
                    <span className="text-sm font-medium">{fmtFull(amt)}</span>
                  </div>
                ))}
            </div>
          </section>
        )}

        {/* Transactions table */}
        <section>
          <h2 className="text-lg font-medium mb-4">Transactions <span className="text-gray-400 font-normal text-sm">({txns.length})</span></h2>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-5 py-3 text-xs text-gray-500 font-medium">Date</th>
                  <th className="text-left px-5 py-3 text-xs text-gray-500 font-medium">Description</th>
                  <th className="text-left px-5 py-3 text-xs text-gray-500 font-medium">Category</th>
                  <th className="text-left px-5 py-3 text-xs text-gray-500 font-medium">Type</th>
                  <th className="text-right px-5 py-3 text-xs text-gray-500 font-medium">Amount</th>
                  <th className="text-right px-5 py-3 text-xs text-gray-500 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {txns.length === 0 && (
                  <tr><td colSpan={6} className="px-5 py-8 text-center text-gray-400">No transactions in this date range.</td></tr>
                )}
                {txns.map(t => (
                  <tr key={t.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 text-gray-500 whitespace-nowrap">
                      {new Date(t.date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                    </td>
                    <td className="px-5 py-3 text-gray-900 max-w-xs truncate">{t.description || "—"}</td>
                    <td className="px-5 py-3 text-gray-500 max-w-xs truncate">{t.category || <span className="text-amber-500">uncategorized</span>}</td>
                    <td className="px-5 py-3 text-gray-600 capitalize">{t.type}</td>
                    <td className={`px-5 py-3 text-right font-medium ${t.type === "revenue" ? "text-teal-700" : "text-gray-700"}`}>
                      {t.type !== "revenue" ? "-" : ""}{fmtFull(t.amount)}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${t.status === "settled" ? "bg-teal-50 text-teal-700" : "bg-amber-50 text-amber-700"}`}>
                        {t.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {qbStatus && !qbStatus.connected && (
          <section className="bg-amber-50 border border-amber-200 rounded-xl p-5 flex items-center justify-between">
            <div>
              <p className="font-medium text-amber-900">QuickBooks not connected</p>
              <p className="text-sm text-amber-700 mt-0.5">Connect your account to start syncing transactions.</p>
            </div>
            <a href={`${API_URL}/api/v1/quickbooks/connect`}
              className="bg-amber-700 hover:bg-amber-800 text-white text-sm rounded-lg px-4 py-2">
              Connect QuickBooks
            </a>
          </section>
        )}
      </main>
    </div>
  );
}
