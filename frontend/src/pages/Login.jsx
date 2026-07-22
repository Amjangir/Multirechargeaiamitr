import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { ShieldCheck, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const res = await login(email, password);
    setBusy(false);
    if (res.ok) {
      toast.success(`Welcome back, ${res.user.name}`);
      nav("/dashboard");
    } else {
      toast.error(res.error);
    }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2 relative z-10">
      <div className="hidden md:block relative">
        <img src="https://images.pexels.com/photos/29506609/pexels-photo-29506609.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
             alt="" className="w-full h-full object-cover opacity-40" />
        <div className="absolute inset-0 flex flex-col justify-end p-12">
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">Fintech console</div>
          <h1 className="text-4xl lg:text-5xl font-bold tracking-tight mt-3 max-w-md" style={{ fontFamily: "Outfit" }}>
            One command center for<br />your recharge network.
          </h1>
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-sm">
          <Link to="/" className="flex items-center gap-2 mb-10">
            <div className="w-8 h-8 rounded-md accent-bg flex items-center justify-center"><ShieldCheck size={16} /></div>
            <span className="font-semibold text-lg" style={{ fontFamily: "Outfit" }}>RechargePro</span>
          </Link>
          <h2 className="text-2xl font-semibold" style={{ fontFamily: "Outfit" }}>Sign in to your account</h2>
          <p className="text-slate-400 text-sm mt-2">Access your role-based cockpit.</p>

          <div className="mt-8 space-y-4">
            <label className="block">
              <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Email</span>
              <input data-testid="login-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                     className="input-dark mt-2" placeholder="you@company.com" />
            </label>
            <label className="block">
              <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Password</span>
              <input data-testid="login-password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                     className="input-dark mt-2" placeholder="••••••••" />
            </label>
            <button data-testid="login-submit" disabled={busy} className="btn-primary w-full flex justify-center items-center gap-2">
              {busy && <Loader2 size={16} className="animate-spin" />} Sign in
            </button>

            <div className="relative flex items-center gap-3 py-1">
              <div className="flex-1 divider" />
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">or</div>
              <div className="flex-1 divider" />
            </div>

            <button
              type="button"
              data-testid="google-login-btn"
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
              Continue with Google
            </button>
          </div>

          <div className="mt-6 text-sm text-slate-400 text-center flex items-center justify-between">
            <Link to="/forgot-password" data-testid="forgot-link" className="text-cyan-300 hover:underline">Forgot password?</Link>
            <Link to="/signup" data-testid="goto-signup" className="text-cyan-300 hover:underline">Create account</Link>
          </div>
          <div className="mt-8 p-3 rounded-lg bg-cyan-400/5 border border-cyan-400/20 text-xs text-slate-300">
            <div className="font-semibold text-cyan-300 mb-1">Admin demo</div>
            admin@rechargepro.com / Admin@12345
          </div>
        </form>
      </div>
    </div>
  );
}
