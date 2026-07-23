import { useEffect, useState } from "react";
import { api, ROLE_LABELS, SERVICES } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid, LineChart, Line, Legend } from "recharts";
import { CalendarDays } from "lucide-react";

function ymd(d) { return d.toISOString().slice(0, 10); }

export default function Reports() {
  const [range, setRange] = useState(() => {
    const end = new Date();
    const start = new Date(); start.setDate(end.getDate() - 29);
    return { start: ymd(start), end: ymd(end) };
  });
  const [data, setData] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams();
    if (range.start) params.set("start", range.start);
    if (range.end) params.set("end", range.end + "T23:59:59Z");
    api.get(`/reports/summary?${params.toString()}`).then((r) => setData(r.data));
  }, [range]);

  const roleRows = data?.by_role || [];
  const totalCount = roleRows.reduce((a, r) => a + r.count, 0);
  const totalAmount = roleRows.reduce((a, r) => a + r.amount, 0);
  const totalCommission = roleRows.reduce((a, r) => a + r.commission, 0);
  const daily = (data?.daily || []).map((d) => ({ day: d._id.slice(5), amount: d.amount, commission: d.commission }));

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">Insights</div>
          <h1 className="text-3xl font-semibold mt-1" style={{ fontFamily: "Outfit" }}>Reports</h1>
        </div>
        <div className="flex items-end gap-3 w-full sm:w-auto">
          <label className="block flex-1 sm:flex-none">
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-500 flex items-center gap-1"><CalendarDays size={12} /> From</span>
            <input data-testid="report-start" type="date" value={range.start} onChange={(e) => setRange({ ...range, start: e.target.value })} className="input-dark mt-1 w-full" />
          </label>
          <label className="block flex-1 sm:flex-none">
            <span className="text-[10px] uppercase tracking-[0.2em] text-slate-500">To</span>
            <input data-testid="report-end" type="date" value={range.end} onChange={(e) => setRange({ ...range, end: e.target.value })} className="input-dark mt-1 w-full" />
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Kpi label="Recharges" value={totalCount} testid="kpi-count" />
        <Kpi label="Volume" value={`₹ ${totalAmount.toFixed(2)}`} testid="kpi-amount" />
        <Kpi label="Commission" value={`₹ ${totalCommission.toFixed(2)}`} testid="kpi-commission" accent="green" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card-surface p-6">
          <h3 className="text-lg font-semibold" style={{ fontFamily: "Outfit" }}>Daily volume & commission</h3>
          <div className="h-72 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="day" stroke="#64748B" fontSize={12} />
                <YAxis stroke="#64748B" fontSize={12} />
                <Tooltip contentStyle={{ background: "#0D111C", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, color: "white" }} />
                <Legend wrapperStyle={{ color: "#94A3B8" }} />
                <Line type="monotone" dataKey="amount" stroke="#00E5FF" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="commission" stroke="#00E676" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card-surface p-6">
          <h3 className="text-lg font-semibold" style={{ fontFamily: "Outfit" }}>By slab (₹)</h3>
          <div className="h-72 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.by_slab || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="label" stroke="#64748B" fontSize={11} />
                <YAxis stroke="#64748B" fontSize={12} />
                <Tooltip contentStyle={{ background: "#0D111C", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, color: "white" }} />
                <Bar dataKey="amount" fill="#7000FF" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Table title="By role" testid="table-by-role" rows={data?.by_role || []} cols={[
          { key: "role", label: "Role", render: (r) => ROLE_LABELS[r.role] || r.role },
          { key: "count", label: "Recharges", right: true },
          { key: "amount", label: "Volume", right: true, render: (r) => `₹ ${r.amount.toFixed(2)}` },
          { key: "commission", label: "Commission", right: true, accent: true, render: (r) => `₹ ${r.commission.toFixed(2)}` },
        ]} />
        <Table title="By service" testid="table-by-service" rows={data?.by_service || []} cols={[
          { key: "service", label: "Service", render: (r) => (SERVICES.find((s) => s.code === r.service)?.name || r.service) },
          { key: "count", label: "Recharges", right: true },
          { key: "amount", label: "Volume", right: true, render: (r) => `₹ ${r.amount.toFixed(2)}` },
          { key: "commission", label: "Commission", right: true, accent: true, render: (r) => `₹ ${r.commission.toFixed(2)}` },
        ]} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Table title="Top users" testid="table-by-user" rows={data?.by_user || []} cols={[
          { key: "user_name", label: "User" },
          { key: "user_role", label: "Role", render: (r) => ROLE_LABELS[r.user_role] || r.user_role },
          { key: "amount", label: "Volume", right: true, render: (r) => `₹ ${r.amount.toFixed(2)}` },
          { key: "commission", label: "Commission", right: true, accent: true, render: (r) => `₹ ${r.commission.toFixed(2)}` },
        ]} />
        <Table title="By operator" testid="table-by-operator" rows={data?.by_operator || []} cols={[
          { key: "service", label: "Service", render: (r) => (SERVICES.find((s) => s.code === r.service)?.name || r.service) },
          { key: "operator", label: "Operator", render: (r) => (r.operator || "").replace("_", " ") },
          { key: "count", label: "Recharges", right: true },
          { key: "amount", label: "Volume", right: true, render: (r) => `₹ ${r.amount.toFixed(2)}` },
        ]} />
      </div>
    </div>
  );
}

function Kpi({ label, value, testid, accent }) {
  return (
    <div className="card-elevated p-6" data-testid={testid}>
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className={`mt-3 text-3xl font-semibold font-mono ${accent === "green" ? "text-emerald-300" : "accent-text"}`}>{value}</div>
    </div>
  );
}

function Table({ title, testid, rows, cols }) {
  return (
    <div className="card-surface overflow-x-auto" data-testid={testid}>
      <div className="p-5 border-b border-white/5">
        <h3 className="text-lg font-semibold" style={{ fontFamily: "Outfit" }}>{title}</h3>
      </div>
      <table className="w-full text-sm min-w-[520px]">
        <thead className="bg-white/[0.03] text-xs uppercase tracking-[0.15em] text-slate-500">
          <tr>
            {cols.map((c) => (<th key={c.key} className={`p-3 ${c.right ? "text-right" : "text-left"}`}>{c.label}</th>))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {rows.length === 0 && (<tr><td colSpan={cols.length} className="p-8 text-center text-slate-500">No data.</td></tr>)}
          {rows.map((r, i) => (
            <tr key={i} className="hover:bg-white/5">
              {cols.map((c) => (
                <td key={c.key} className={`p-3 ${c.right ? "text-right font-mono" : ""} ${c.accent ? "text-emerald-300" : ""}`}>
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
