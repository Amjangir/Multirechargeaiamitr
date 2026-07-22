import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { ShieldCheck, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function Signup() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ name: "", email: "", password: "", phone: "" });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const res = await register({ ...f, role: "retailer" });
    setBusy(false);
    if (res.ok) {
      toast.success("Account created");
      nav("/dashboard");
    } else {
      toast.error(res.error);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8 relative z-10">
      <form onSubmit={submit} className="w-full max-w-md card-elevated p-8">
        <Link to="/" className="flex items-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-md accent-bg flex items-center justify-center"><ShieldCheck size={16} /></div>
          <span className="font-semibold text-lg" style={{ fontFamily: "Outfit" }}>RechargePro</span>
        </Link>
        <h2 className="text-2xl font-semibold" style={{ fontFamily: "Outfit" }}>Create a retailer account</h2>
        <p className="text-slate-400 text-sm mt-2">Distributors and admins are added by their upline.</p>

        <div className="mt-8 space-y-4">
          <Field label="Full name" testid="signup-name" value={f.name} onChange={(v) => setF({ ...f, name: v })} required />
          <Field label="Email" testid="signup-email" type="email" value={f.email} onChange={(v) => setF({ ...f, email: v })} required />
          <Field label="Phone" testid="signup-phone" value={f.phone} onChange={(v) => setF({ ...f, phone: v })} />
          <Field label="Password" testid="signup-password" type="password" value={f.password} onChange={(v) => setF({ ...f, password: v })} required />
          <button data-testid="signup-submit" disabled={busy} className="btn-primary w-full flex justify-center items-center gap-2">
            {busy && <Loader2 size={16} className="animate-spin" />} Create account
          </button>

          <div className="relative flex items-center gap-3 py-1">
            <div className="flex-1 divider" />
            <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">or</div>
            <div className="flex-1 divider" />
          </div>

          <button
            type="button"
            data-testid="google-signup-btn"
            onClick={() => {
              // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
              const redirectUrl = window.location.origin + "/auth/callback";
              window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
            }}
            className="btn-ghost w-full flex items-center justify-center gap-2"
          >
            <svg viewBox="0 0 24 24" width="16" height="16">
              <path fill="#EA4335" d="M12 10.9v3.9h5.4c-.2 1.2-1.4 3.6-5.4 3.6-3.2 0-5.9-2.7-5.9-6s2.7-6 5.9-6c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.7 3.7 14.6 3 12 3 6.9 3 2.8 7.1 2.8 12.2S6.9 21.4 12 21.4c6.9 0 9.4-4.8 9.4-8.6 0-.6-.1-1.1-.1-1.9H12z"/>
            </svg>
            Sign up with Google
          </button>
        </div>
        <div className="mt-6 text-sm text-slate-400 text-center">
          Already registered? <Link to="/login" data-testid="goto-login" className="text-cyan-300 hover:underline">Sign in</Link>
        </div>
      </form>
    </div>
  );
}

function Field({ label, testid, value, onChange, type = "text", required }) {
  return (
    <label className="block">
      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">{label}</span>
      <input data-testid={testid} type={type} required={required} value={value}
             onChange={(e) => onChange(e.target.value)} className="input-dark mt-2" />
    </label>
  );
}
