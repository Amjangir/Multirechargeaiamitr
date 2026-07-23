import { useEffect, useState } from "react";
import { api, formatErr, ROLE_LABELS, SERVICES } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Loader2 } from "lucide-react";

export default function Commissions() {
  const [rules, setRules] = useState([]);
  const [operators, setOperators] = useState({});
  const [users, setUsers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ scope: "role", role: "retailer", user_id: "", service: "", operator: "", rate: "2", min_amount: "0", max_amount: "" });

  const load = () => {
    api.get("/commissions").then((r) => setRules(r.data));
  };
  useEffect(() => {
    load();
    api.get("/operators").then((r) => setOperators(r.data));
    api.get("/users").then((r) => setUsers(r.data));
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const body = {
      service: f.service || null,
      operator: f.operator || null,
      user_id: f.scope === "user" ? f.user_id : null,
      role: f.scope === "role" ? f.role : null,
      rate: parseFloat(f.rate) / 100,
      min_amount: parseFloat(f.min_amount || "0"),
      max_amount: f.max_amount === "" ? null : parseFloat(f.max_amount),
    };
    try {
      await api.post("/commissions", body);
      toast.success("Rule saved");
      setF({ ...f, rate: "2", min_amount: "0", max_amount: "" });
      load();
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  const del = async (id) => {
    try {
      await api.delete(`/commissions/${id}`);
      toast.success("Rule removed");
      load();
    } catch (e) { toast.error(formatErr(e)); }
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">Admin</div>
        <h1 className="text-3xl font-semibold mt-1" style={{ fontFamily: "Outfit" }}>Commission rules</h1>
        <p className="text-sm text-slate-400 mt-2">Rules are matched most-specific first: user + service + operator → user + service → user → service + operator → service → role → default (2%).</p>
      </div>

      <form onSubmit={submit} className="card-elevated p-6 grid md:grid-cols-6 gap-3">
        <label className="block md:col-span-1">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Scope</span>
          <select data-testid="cm-scope" value={f.scope} onChange={(e) => setF({ ...f, scope: e.target.value })} className="input-dark mt-2">
            <option value="role">Role</option>
            <option value="user">User</option>
            <option value="global">Global (service/operator)</option>
          </select>
        </label>
        {f.scope === "role" && (
          <label className="block md:col-span-1">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Role</span>
            <select data-testid="cm-role" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} className="input-dark mt-2">
              {Object.entries(ROLE_LABELS).map(([k, v]) => (<option key={k} value={k}>{v}</option>))}
            </select>
          </label>
        )}
        {f.scope === "user" && (
          <label className="block md:col-span-2">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">User</span>
            <select data-testid="cm-user" value={f.user_id} onChange={(e) => setF({ ...f, user_id: e.target.value })} className="input-dark mt-2" required>
              <option value="">Select user…</option>
              {users.map((u) => (<option key={u.user_id} value={u.user_id}>{u.name} · {ROLE_LABELS[u.role]}</option>))}
            </select>
          </label>
        )}
        <label className="block md:col-span-1">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Service</span>
          <select data-testid="cm-service" value={f.service} onChange={(e) => setF({ ...f, service: e.target.value, operator: "" })} className="input-dark mt-2">
            <option value="">Any</option>
            {SERVICES.map((s) => (<option key={s.code} value={s.code}>{s.name}</option>))}
          </select>
        </label>
        <label className="block md:col-span-1">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Operator</span>
          <select data-testid="cm-operator" value={f.operator} onChange={(e) => setF({ ...f, operator: e.target.value })} className="input-dark mt-2" disabled={!f.service}>
            <option value="">Any</option>
            {(operators[f.service] || []).map((o) => (<option key={o.code} value={o.code}>{o.name}</option>))}
          </select>
        </label>
        <label className="block md:col-span-1">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Rate (%)</span>
          <input data-testid="cm-rate" required type="number" min="0" max="100" step="0.01" value={f.rate} onChange={(e) => setF({ ...f, rate: e.target.value })} className="input-dark mt-2" />
        </label>
        <label className="block md:col-span-1">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Min ₹</span>
          <input data-testid="cm-min" type="number" min="0" step="1" value={f.min_amount} onChange={(e) => setF({ ...f, min_amount: e.target.value })} className="input-dark mt-2" placeholder="0" />
        </label>
        <label className="block md:col-span-1">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Max ₹ (empty = ∞)</span>
          <input data-testid="cm-max" type="number" min="0" step="1" value={f.max_amount} onChange={(e) => setF({ ...f, max_amount: e.target.value })} className="input-dark mt-2" placeholder="∞" />
        </label>
        <div className="md:col-span-6 flex justify-end">
          <button data-testid="cm-submit" disabled={busy} className="btn-primary flex items-center gap-2">
            {busy && <Loader2 size={16} className="animate-spin" />} <Plus size={16} /> Add rule
          </button>
        </div>
      </form>

      <div className="card-surface overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.03] text-xs uppercase tracking-[0.15em] text-slate-500">
            <tr>
              <th className="text-left p-4">Scope</th>
              <th className="text-left p-4">Target</th>
              <th className="text-left p-4">Service</th>
              <th className="text-left p-4">Operator</th>
              <th className="text-left p-4">Slab (₹)</th>
              <th className="text-right p-4">Rate</th>
              <th className="text-right p-4">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rules.length === 0 && (<tr><td colSpan="7" className="p-8 text-center text-slate-500">No custom rules. Default 2% applied.</td></tr>)}
            {rules.map((r) => {
              const scope = r.user_id ? "User" : r.role ? "Role" : "Global";
              const target = r.user_id ? (users.find((u) => u.user_id === r.user_id)?.name || r.user_id) : (r.role ? ROLE_LABELS[r.role] : "—");
              const slab = `${r.min_amount ?? 0} – ${r.max_amount == null ? "∞" : r.max_amount}`;
              return (
                <tr key={r.id} className="hover:bg-white/5">
                  <td className="p-4">{scope}</td>
                  <td className="p-4">{target}</td>
                  <td className="p-4 capitalize">{r.service ? r.service.replace("_", " ") : "Any"}</td>
                  <td className="p-4 capitalize">{r.operator || "Any"}</td>
                  <td className="p-4 font-mono text-xs text-slate-300">{slab}</td>
                  <td className="p-4 text-right font-mono text-cyan-300">{(r.rate * 100).toFixed(2)}%</td>
                  <td className="p-4 text-right">
                    <button data-testid={`cm-del-${r.id}`} onClick={() => del(r.id)} className="btn-ghost text-xs inline-flex items-center gap-1">
                      <Trash2 size={13} /> Remove
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
