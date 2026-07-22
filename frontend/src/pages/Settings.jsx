import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { api, formatErr, ROLE_LABELS } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, KeyRound, UserPen } from "lucide-react";

export default function Settings() {
  const { user, refresh } = useAuth();
  const [f, setF] = useState({ name: user.name, phone: user.phone || "" });
  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const [pwBusy, setPwBusy] = useState(false);

  const saveProfile = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.patch("/me", { name: f.name, phone: f.phone });
      await refresh();
      toast.success("Profile updated");
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(false); }
  };

  const changePw = async (e) => {
    e.preventDefault();
    if (pw.next.length < 6) return toast.error("Password must be at least 6 characters");
    if (pw.next !== pw.confirm) return toast.error("Passwords don't match");
    setPwBusy(true);
    try {
      await api.patch("/me", { password: pw.next });
      toast.success("Password changed");
      setPw({ current: "", next: "", confirm: "" });
    } catch (e) { toast.error(formatErr(e)); } finally { setPwBusy(false); }
  };

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">Settings</div>
        <h1 className="text-3xl font-semibold mt-1" style={{ fontFamily: "Outfit" }}>Profile & preferences</h1>
      </div>

      <form onSubmit={saveProfile} className="card-elevated p-6 space-y-4">
        <div className="flex items-center gap-2 text-slate-300">
          <UserPen size={16} /> <div className="text-sm font-medium">Personal information</div>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Name</span>
            <input data-testid="me-name" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input-dark mt-2" />
          </label>
          <label className="block">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Phone</span>
            <input data-testid="me-phone" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} className="input-dark mt-2" />
          </label>
          <ReadRow k="Email" v={user.email} />
          <ReadRow k="Role" v={ROLE_LABELS[user.role]} />
        </div>
        <div className="flex justify-end">
          <button data-testid="me-save" disabled={busy} className="btn-primary flex items-center gap-2">
            {busy && <Loader2 size={16} className="animate-spin" />} Save changes
          </button>
        </div>
      </form>

      <form onSubmit={changePw} className="card-surface p-6 space-y-4">
        <div className="flex items-center gap-2 text-slate-300">
          <KeyRound size={16} /> <div className="text-sm font-medium">Change password</div>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <label className="block md:col-span-2">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">New password</span>
            <input data-testid="pw-new" required type="password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} className="input-dark mt-2" />
          </label>
          <label className="block md:col-span-2">
            <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Confirm new password</span>
            <input data-testid="pw-confirm" required type="password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} className="input-dark mt-2" />
          </label>
        </div>
        <div className="flex justify-end">
          <button data-testid="pw-save" disabled={pwBusy} className="btn-primary flex items-center gap-2">
            {pwBusy && <Loader2 size={16} className="animate-spin" />} Update password
          </button>
        </div>
      </form>
    </div>
  );
}

function ReadRow({ k, v }) {
  return (
    <label className="block">
      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{k}</span>
      <div className="input-dark mt-2 text-slate-400 pointer-events-none">{v}</div>
    </label>
  );
}
