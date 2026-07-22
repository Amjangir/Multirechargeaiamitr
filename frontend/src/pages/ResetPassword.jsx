import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, formatErr } from "@/lib/api";
import { toast } from "sonner";
import { ShieldCheck, Loader2 } from "lucide-react";

export default function ResetPassword() {
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const [token, setToken] = useState(sp.get("token") || "");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (pw !== pw2) return toast.error("Passwords don't match");
    setBusy(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: pw });
      toast.success("Password updated. You can sign in now.");
      nav("/login");
    } catch (e) {
      toast.error(formatErr(e));
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8 relative z-10">
      <form onSubmit={submit} className="w-full max-w-md card-elevated p-8">
        <div className="flex items-center gap-2 mb-6">
          <div className="w-8 h-8 rounded-md accent-bg flex items-center justify-center"><ShieldCheck size={16} /></div>
          <span className="font-semibold text-lg" style={{ fontFamily: "Outfit" }}>Set new password</span>
        </div>
        <label className="block">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Reset token</span>
          <input data-testid="reset-token" required value={token} onChange={(e) => setToken(e.target.value)} className="input-dark mt-2 font-mono text-xs" />
        </label>
        <label className="block mt-4">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">New password</span>
          <input data-testid="reset-password" required type="password" value={pw} onChange={(e) => setPw(e.target.value)} className="input-dark mt-2" />
        </label>
        <label className="block mt-4">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Confirm password</span>
          <input data-testid="reset-password2" required type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} className="input-dark mt-2" />
        </label>
        <button data-testid="reset-submit" disabled={busy} className="btn-primary w-full mt-6 flex justify-center items-center gap-2">
          {busy && <Loader2 size={16} className="animate-spin" />} Update password
        </button>
        <div className="mt-6 text-sm text-slate-400 text-center">
          <Link to="/login" className="text-cyan-300 hover:underline">Back to sign in</Link>
        </div>
      </form>
    </div>
  );
}
