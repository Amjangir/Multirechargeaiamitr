import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Transactions() {
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  const [service, setService] = useState("");

  const load = () => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (service) params.set("service", service);
    api.get(`/transactions?${params.toString()}`).then((r) => setRows(r.data));
  };
  useEffect(() => { load(); }, [status, service]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">History</div>
          <h1 className="text-3xl font-semibold mt-1" style={{ fontFamily: "Outfit" }}>Transactions</h1>
        </div>
        <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
          <select data-testid="filter-status" value={status} onChange={(e) => setStatus(e.target.value)} className="input-dark sm:w-40">
            <option value="">All statuses</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
          </select>
          <select data-testid="filter-service" value={service} onChange={(e) => setService(e.target.value)} className="input-dark sm:w-44">
            <option value="">All services</option>
            <option value="mobile_prepaid">Mobile Prepaid</option>
            <option value="dth">DTH</option>
            <option value="electricity">Electricity</option>
            <option value="data_card">Data Card</option>
          </select>
        </div>
      </div>

      <div className="card-surface overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
          <thead className="bg-white/[0.03] text-xs uppercase tracking-[0.15em] text-slate-500">
            <tr>
              <th className="text-left p-4">Ref</th>
              <th className="text-left p-4">Service</th>
              <th className="text-left p-4">Operator</th>
              <th className="text-left p-4">Number</th>
              <th className="text-left p-4">User</th>
              <th className="text-right p-4">Amount</th>
              <th className="text-right p-4">Commission</th>
              <th className="text-left p-4">Status</th>
              <th className="text-left p-4">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.length === 0 && (
              <tr><td colSpan="9" className="p-8 text-center text-slate-500">No transactions match your filter.</td></tr>
            )}
            {rows.map((t) => (
              <tr key={t.id} className="hover:bg-white/5">
                <td className="p-4 font-mono text-xs">{t.operator_ref}</td>
                <td className="p-4 capitalize">{t.service.replace("_", " ")}</td>
                <td className="p-4 capitalize">{t.operator.replace("_", " ")}</td>
                <td className="p-4 font-mono">{t.number}</td>
                <td className="p-4">{t.user_name}</td>
                <td className="p-4 text-right font-mono">₹ {t.amount.toFixed(2)}</td>
                <td className="p-4 text-right font-mono text-emerald-300">₹ {(t.commission || 0).toFixed(2)}</td>
                <td className="p-4">
                  <span className={`text-[10px] uppercase tracking-[0.2em] px-2 py-1 rounded-full ${t.status === "success" ? "bg-emerald-400/10 text-emerald-300" : "bg-red-400/10 text-red-300"}`}>
                    {t.status}
                  </span>
                </td>
                <td className="p-4 text-slate-400">{new Date(t.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
