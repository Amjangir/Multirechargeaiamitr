import { useAuth } from "@/contexts/AuthContext";
import { ROLE_LABELS } from "@/lib/api";

export default function Settings() {
  const { user } = useAuth();
  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">Settings</div>
        <h1 className="text-3xl font-semibold mt-1" style={{ fontFamily: "Outfit" }}>Profile & preferences</h1>
      </div>
      <div className="card-surface p-6 space-y-4">
        <Row k="Name" v={user.name} />
        <Row k="Email" v={user.email} />
        <Row k="Role" v={ROLE_LABELS[user.role]} />
        <Row k="Phone" v={user.phone || "—"} />
        <Row k="Status" v={user.status} />
        <Row k="Member since" v={new Date(user.created_at).toLocaleDateString()} />
      </div>

      <div className="card-surface p-6">
        <h3 className="text-lg font-semibold mb-2" style={{ fontFamily: "Outfit" }}>Operator commissions</h3>
        <p className="text-sm text-slate-400">Currently pegged at a flat <span className="text-cyan-300 font-mono">2%</span> on every successful recharge. Configurable rules per operator/service can be added by the admin.</p>
      </div>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex items-center justify-between border-b border-white/5 pb-3 last:border-0">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{k}</div>
      <div className="text-sm">{v}</div>
    </div>
  );
}
