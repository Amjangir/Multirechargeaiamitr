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
