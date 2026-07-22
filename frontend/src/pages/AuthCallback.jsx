import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api, formatErr } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
  const nav = useNavigate();
  const { refresh } = useAuth();
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;
    const hash = window.location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    if (!match) { nav("/login"); return; }
    const sessionId = decodeURIComponent(match[1]);
    (async () => {
      try {
        const { data } = await api.post("/auth/session", { session_id: sessionId });
        localStorage.setItem("rp_token", data.token);
        await refresh();
        toast.success(`Signed in as ${data.user.name}`);
        window.history.replaceState({}, "", "/dashboard");
        nav("/dashboard", { replace: true });
      } catch (e) {
        toast.error(formatErr(e));
        nav("/login");
      }
    })();
  }, [nav, refresh]);

  return (
    <div className="min-h-screen flex items-center justify-center relative z-10">
      <div className="flex items-center gap-3 text-slate-300">
        <Loader2 className="animate-spin text-cyan-400" size={22} />
        Completing sign-in…
      </div>
    </div>
  );
}
