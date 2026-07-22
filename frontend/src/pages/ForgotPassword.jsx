import { useState } from "react";
import { Link } from "react-router-dom";
import { api, formatErr } from "@/lib/api";
import { toast } from "sonner";
import { ShieldCheck, Loader2, ArrowLeft } from "lucide-react";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/auth/forgot-password", { email });
      if (data.reset_token) {
        setToken(data.reset_token);
        toast.success("Reset link generated");
      } else {
        toast.info("If the email exists we've sent a reset link.");
      }
    } catch (e) {
      toast.error(formatErr(e));
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8 relative z-10">
      <form onSubmit={submit} className="w-full max-w-md card-elevated p-8">
        <Link to="/login" className="flex items-center gap-2 text-slate-400 hover:text-white text-sm mb-6">
          <ArrowLeft size={14} /> Back to sign in
        </Link>
        <div className="flex items-center gap-2 mb-6">
          <div className="w-8 h-8 rounded-md accent-bg flex items-center justify-center"><ShieldCheck size={16} /></div>
          <span className="font-semibold text-lg" style={{ fontFamily: "Outfit" }}>Forgot password</span>
        </div>
        <p className="text-slate-400 text-sm">Enter your email and we'll generate a reset link. In this demo, the link is shown below.</p>
        <label className="block mt-6">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Email</span>
          <input data-testid="forgot-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                 className="input-dark mt-2" placeholder="you@company.com" />
        </label>
        <button data-testid="forgot-submit" disabled={busy} className="btn-primary w-full mt-6 flex justify-center items-center gap-2">
          {busy && <Loader2 size={16} className="animate-spin" />} Send reset link
        </button>

        {token && (
          <div className="mt-6 p-4 rounded-lg bg-cyan-400/5 border border-cyan-400/20" data-testid="reset-token-box">
            <div className="text-xs uppercase tracking-[0.2em] text-cyan-300 mb-2">Demo reset link</div>
            <Link to={`/reset-password?token=${token}`} className="text-cyan-300 hover:underline text-sm break-all font-mono">/reset-password?token={token}</Link>
          </div>
        )}
      </form>
    </div>
  );
}
