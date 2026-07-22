import { useEffect, useState } from "react";
import { api, ROLE_LABELS } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";
import { Plus, Loader2, ShieldOff, ShieldCheck } from "lucide-react";

const CREATABLE_ROLES = {
  admin: ["master_distributor", "distributor", "retailer"],
  master_distributor: ["distributor", "retailer"],
  distributor: ["retailer"],
};

export default function UsersPage() {
  const { user } = useAuth();
  const [rows, setRows] = useState([]);
  const [showCreate, setShowCreate] = useState(false);

  const load = () => { api.get("/users").then((r) => setRows(r.data)); };
  useEffect(() => { load(); }, []);

  const toggle = async (u) => {
    const next = u.status === "active" ? "blocked" : "active";
    try {
      await api.patch(`/users/${u.user_id}/status?status=${next}`);
      toast.success(`${u.name} is now ${next}`);
      load();
    } catch (e) { toast.error("Failed to update"); }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">Network</div>
          <h1 className="text-3xl font-semibold mt-1" style={{ fontFamily: "Outfit" }}>Your downline</h1>
        </div>
        {CREATABLE_ROLES[user.role] && (
          <button data-testid="add-user-btn" onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
            <Plus size={16} /> Add user
          </button>
        )}
      </div>

      <div className="card-surface overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-white/[0.03] text-xs uppercase tracking-[0.15em] text-slate-500">
            <tr>
              <th className="text-left p-4">Name</th>
              <th className="text-left p-4">Email</th>
              <th className="text-left p-4">Role</th>
              <th className="text-left p-4">Phone</th>
              <th className="text-right p-4">Wallet</th>
              <th className="text-left p-4">Status</th>
              <th className="text-right p-4">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.length === 0 && (
              <tr><td colSpan="7" className="p-8 text-center text-slate-500">No users in your network yet.</td></tr>
            )}
            {rows.map((u) => (
              <tr key={u.user_id} className="hover:bg-white/5">
                <td className="p-4 font-medium">{u.name}</td>
                <td className="p-4 text-slate-400">{u.email}</td>
                <td className="p-4">
                  <span className="text-xs px-2 py-1 rounded-full bg-cyan-400/10 text-cyan-300">{ROLE_LABELS[u.role]}</span>
                </td>
                <td className="p-4 text-slate-400">{u.phone || "—"}</td>
                <td className="p-4 text-right font-mono">₹ {u.wallet_balance.toFixed(2)}</td>
                <td className="p-4">
                  <span className={`text-[10px] uppercase tracking-[0.2em] ${u.status === "active" ? "text-emerald-300" : "text-red-300"}`}>{u.status}</span>
                </td>
                <td className="p-4 text-right">
                  {u.user_id !== user.user_id && u.role !== "admin" && (
                    <button data-testid={`toggle-${u.user_id}`} onClick={() => toggle(u)} className="btn-ghost text-xs inline-flex items-center gap-1">
                      {u.status === "active" ? <ShieldOff size={13} /> : <ShieldCheck size={13} />}
                      {u.status === "active" ? "Block" : "Unblock"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <CreateUserModal user={user} onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); load(); }} />
      )}
    </div>
  );
}

function CreateUserModal({ user, onClose, onCreated }) {
  const roles = CREATABLE_ROLES[user.role] || [];
  const [f, setF] = useState({ name: "", email: "", password: "", phone: "", role: roles[0] });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/users", f);
      toast.success("User created");
      onCreated();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <form onSubmit={submit} className="card-elevated p-8 w-full max-w-md space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-semibold" style={{ fontFamily: "Outfit" }}>Add new user</h3>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-white text-sm">Cancel</button>
        </div>
        <select data-testid="create-role" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} className="input-dark">
          {roles.map((r) => (<option key={r} value={r}>{ROLE_LABELS[r]}</option>))}
        </select>
        <input data-testid="create-name" required placeholder="Full name" className="input-dark" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <input data-testid="create-email" type="email" required placeholder="Email" className="input-dark" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
        <input data-testid="create-phone" placeholder="Phone" className="input-dark" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
        <input data-testid="create-password" type="password" required placeholder="Password" className="input-dark" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
        <button data-testid="create-submit" disabled={busy} className="btn-primary w-full flex items-center gap-2 justify-center">
          {busy && <Loader2 size={16} className="animate-spin" />} Create
        </button>
      </form>
    </div>
  );
}
