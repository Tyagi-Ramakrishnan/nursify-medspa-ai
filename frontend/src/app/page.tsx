"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import {
  isLoggedIn, logout, getTodayReport, getLast7Days,
  getTransactions, getQBStatus, triggerSync, triggerReport,
} from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function fmtFull(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export default function Dashboard() {
  const router = useRouter();
  const [today, setToday] = useState<any>(null);
  const [week, setWeek] = useState<any[]>([]);
  const [txns, setTxns] = useState<any[]>([]);
  const [qbStatus, setQbStatus] = useState<any>(null);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!isLoggedIn()) { router.replace("/login"); return; }
    loadAll();
  }, []);

  async function loadAll() {
    try {
      const [t, w, tx, qb] = await Promise.all([
        getTodayReport(),
        getLast7Days(),
        getTransactions({ limit: "20" }),
        getQBStatus(),
      ]);
      setToday(t);
      setWeek(w);
      setTxns(tx.transactions || []);
      setQbStatus(qb);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleSync() {
    setSyncing(true);
    setMessage("");
    try {
      await triggerSync();
      await loadAll();
      setMessage("Sync complete");
    } catch {
      setMessage("Sync failed — check QuickBooks connection");
    } finally {
      setSyncing(false);
    }
  }

  async function handleGenerateReport() {
    try {
      await triggerReport(true);
      setMessage("Report generated and email sent");
      await loadAll();
    } catch {
      setMessage("Report generation failed");
    }
  }

  return (
    <div className="min-h-screen">
      {/* Nav */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div>
          <span className="text-xs uppercase tracking-widest text-teal-700 font-medium">Nursify MedSpa AI</span>
        </div>
        <div className="flex items-center gap-4">
          {qbStatus && (
            <span className={`text-xs px-2 py-1 rounded-full ${qbStatus.connected ? "bg-teal-50 text-teal-700" : "bg-red-50 text-red-600"}`}>
              QB {qbStatus.connected ? "connected" : "disconnected"}
            </span>
          )}
          <button onClick={handleSync} disabled={syncing}
            className="text-sm text-gray-600 hover:text-gray-900 border border-gray-200 rounded-lg px-3 py-1.5 transition-colors disabled:opacity-40">
            {syncing ? "Syncing…" : "Sync now"}
          </button>
          <button onClick={logout} className="text-sm text-gray-400 hover:text-gray-600">Sign out</button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        {message && (
          <div className="text-sm text-teal-700 bg-teal-50 border border-teal-200 rounded-lg px-4 py-2">
            {message}
          </div>
        )}

        {/* Today's summary cards */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium">
              Today — {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
            </h2>
            <button onClick={handleGenerateReport}
              className="text-sm text-teal-700 hover:text-teal-900 border border-teal-200 rounded-lg px-3 py-1.5">
              Send report email
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Revenue", value: today?.total_revenue ?? 0, color: "text-teal-700" },
              { label: "Expenses", value: today?.total_expenses ?? 0, color: "text-gray-700" },
              { label: "Fees", value: today?.total_fees ?? 0, color: "text-gray-700" },
              { label: "Net income", value: today?.net_income ?? 0, color: today?.net_income >= 0 ? "text-teal-700" : "text-red-600" },
            ].map((card) => (
              <div key={card.label} className="bg-white rounded-xl border border-gray-200 p-4">
                <p className="text-xs text-gray-500 mb-1">{card.label}</p>
                <p className={`text-2xl font-medium ${card.color}`}>{fmt(card.value)}</p>
              </div>
            ))}
          </div>
          {today && (
            <p className="text-xs text-gray-400 mt-2">
              {today.transaction_count} transactions &nbsp;·&nbsp; {today.pending_count} pending
            </p>
          )}
        </section>

        {/* 7-day chart */}
        <section>
          <h2 className="text-lg font-medium mb-4">Last 7 days</h2>
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={week} barSize={32}>
                <XAxis dataKey="date" tickFormatter={(d) => new Date(d + "T00:00:00").toLocaleDateString("en-US", { weekday: "short" })}
                  tick={{ fontSize: 12, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                  tick={{ fontSize: 12, fill: "#9ca3af" }} axisLine={false} tickLine={false} width={48} />
                <Tooltip
                  formatter={(v: number) => [fmtFull(v), "Revenue"]}
                  labelFormatter={(d) => new Date(d + "T00:00:00").toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" })}
                  contentStyle={{ border: "1px solid #e5e7eb", borderRadius: 8, fontSize: 13 }}
                />
                <Bar dataKey="total_revenue" radius={[4, 4, 0, 0]}>
                  {week.map((entry, i) => (
                    <Cell key={i} fill={i === week.length - 1 ? "#0f6e56" : "#9fe1cb"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Category breakdown */}
        {today?.category_breakdown && Object.keys(today.category_breakdown).length > 0 && (
          <section>
            <h2 className="text-lg font-medium mb-4">Revenue by service</h2>
            <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
              {Object.entries(today.category_breakdown as Record<string, number>)
                .sort(([, a], [, b]) => b - a)
                .map(([cat, amt]) => (
                  <div key={cat} className="flex items-center justify-between px-5 py-3">
                    <span className="text-sm text-gray-700 capitalize">{cat}</span>
                    <span className="text-sm font-medium text-gray-900">{fmtFull(amt)}</span>
                  </div>
                ))}
            </div>
          </section>
        )}

        {/* Recent transactions */}
        <section>
          <h2 className="text-lg font-medium mb-4">Recent transactions</h2>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-5 py-3 text-xs text-gray-500 font-medium">Date</th>
                  <th className="text-left px-5 py-3 text-xs text-gray-500 font-medium">Description</th>
                  <th className="text-left px-5 py-3 text-xs text-gray-500 font-medium">Source</th>
                  <th className="text-left px-5 py-3 text-xs text-gray-500 font-medium">Type</th>
                  <th className="text-right px-5 py-3 text-xs text-gray-500 font-medium">Amount</th>
                  <th className="text-right px-5 py-3 text-xs text-gray-500 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {txns.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-5 py-8 text-center text-gray-400 text-sm">
                      No transactions yet. Connect QuickBooks and run a sync.
                    </td>
                  </tr>
                )}
                {txns.map((t) => (
                  <tr key={t.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 text-gray-500 whitespace-nowrap">
                      {new Date(t.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                    </td>
                    <td className="px-5 py-3 text-gray-900 max-w-xs truncate">{t.description || "—"}</td>
                    <td className="px-5 py-3">
                      <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{t.source}</span>
                    </td>
                    <td className="px-5 py-3 text-gray-600 capitalize">{t.type}</td>
                    <td className={`px-5 py-3 text-right font-medium ${t.type === "revenue" ? "text-teal-700" : "text-gray-700"}`}>
                      {t.type === "expense" || t.type === "fee" ? "-" : ""}{fmtFull(t.amount)}
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

        {/* QuickBooks connect prompt if not connected */}
        {qbStatus && !qbStatus.connected && (
          <section className="bg-amber-50 border border-amber-200 rounded-xl p-5 flex items-center justify-between">
            <div>
              <p className="font-medium text-amber-900">QuickBooks not connected</p>
              <p className="text-sm text-amber-700 mt-0.5">Connect your account to start syncing transactions automatically.</p>
            </div>
            <a href={`${process.env.NEXT_PUBLIC_API_URL}/api/v1/quickbooks/connect`}
              className="bg-amber-700 hover:bg-amber-800 text-white text-sm rounded-lg px-4 py-2 whitespace-nowrap">
              Connect QuickBooks
            </a>
          </section>
        )}
      </main>
    </div>
  );
}
