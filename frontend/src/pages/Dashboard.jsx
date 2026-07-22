import { useEffect, useState } from "react";
import { api, ROLE_LABELS, SERVICES } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Link } from "react-router-dom";
import { Wallet, TrendingUp, Receipt, CheckCircle2, XCircle, Smartphone, Tv, Zap, Wifi, ArrowRight } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, CartesianGrid } from "recharts";

const ICON = { Smartphone, Tv, Zap, Wifi };

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [balance, setBalance] = useState(0);
  const [recent, setRecent] = useState([]);

  useEffect(() => {
    api.get("/stats/summary").then((r) => setStats(r.data));
    api.get("/wallet/balance").then((r) => setBalance(r.data.balance));
    api.get("/transactions?limit=6").then((r) => setRecent(r.data));
  }, []);

  const success = stats?.tx?.success || { count: 0, amount: 0, commission: 0 };
  const failed = stats?.tx?.failed || { count: 0, amount: 0, commission: 0 };
  const total = success.count + failed.count;
  const rate = total ? Math.round((success.count / total) * 100) : 0;

  const daily = (stats?.daily || []).map((d) => ({ day: d._id.slice(5), amount: d.amount, count: d.count }));

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">{ROLE_LABELS[user.role]} console</div>
          <h1 className="text-3xl font-semibold mt-1" style={{ fontFamily: "Outfit" }}>Good to see you, {user.name.split(" ")[0]}</h1>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard icon={Wallet} label="Wallet Balance" value={`₹ ${balance.toFixed(2)}`} accent="cyan" testid="metric-wallet" />
        <MetricCard icon={CheckCircle2} label="Successful Recharges" value={success.count} sub={`₹ ${success.amount.toFixed(0)} volume`} accent="green" testid="metric-success" />
        <MetricCard icon={XCircle} label="Failed" value={failed.count} sub={`${rate}% success rate`} accent="red" testid="metric-failed" />
        <MetricCard icon={TrendingUp} label="Commissions Earned" value={`₹ ${(success.commission || 0).toFixed(2)}`} sub="Lifetime" accent="purple" testid="metric-commission" />
      </div>

      {user.role === "admin" && stats?.user_counts && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(stats.user_counts).map(([k, v]) => (
            <div key={k} className="card-surface p-5">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{ROLE_LABELS[k]}s</div>
              <div className="mt-2 text-2xl font-semibold font-mono">{v}</div>
            </div>
          ))}
        </div>
      )}

      {/* Quick Recharge tiles */}
      <div className="card-surface p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold" style={{ fontFamily: "Outfit" }}>Quick recharge</h3>
            <p className="text-xs text-slate-500 mt-1">Jump straight into a top-up flow.</p>
          </div>
          <Link to="/recharge" data-testid="dash-recharge-all" className="text-cyan-300 text-sm hover:underline inline-flex items-center gap-1">
            All services <ArrowRight size={14} />
          </Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {SERVICES.map((s) => {
            const Ic = ICON[s.icon];
            return (
              <Link
                key={s.code}
                to={`/recharge?service=${s.code}`}
                data-testid={`dash-quick-${s.code}`}
                className="card-elevated p-5 hover:border-cyan-400/40 transition-colors block"
              >
                <Ic size={22} className="text-cyan-300" />
                <div className="mt-3 font-medium">{s.name}</div>
                <div className="text-xs text-slate-500 mt-1">Start recharge</div>
              </Link>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card-surface p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold" style={{ fontFamily: "Outfit" }}>Volume — last 7 days</h3>
              <p className="text-xs text-slate-500 mt-1">Recharge amount by day</p>
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="day" stroke="#64748B" fontSize={12} />
                <YAxis stroke="#64748B" fontSize={12} />
                <Tooltip contentStyle={{ background: "#0D111C", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, color: "white" }} />
                <Bar dataKey="amount" fill="#00E5FF" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card-surface p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold" style={{ fontFamily: "Outfit" }}>Recent transactions</h3>
            <Receipt size={18} className="text-slate-500" />
          </div>
          <div className="space-y-3">
            {recent.length === 0 && <div className="text-slate-500 text-sm">No transactions yet.</div>}
            {recent.map((t) => (
              <div key={t.id} className="flex items-center justify-between text-sm border-b border-white/5 pb-3 last:border-0">
                <div>
                  <div className="font-medium">{t.service.replace("_", " ")}</div>
                  <div className="text-xs text-slate-500">{t.number} · {new Date(t.created_at).toLocaleTimeString()}</div>
                </div>
                <div className="text-right">
                  <div className="font-mono">₹ {t.amount.toFixed(0)}</div>
                  <div className={`text-[10px] uppercase tracking-widest ${t.status === "success" ? "text-emerald-400" : "text-red-400"}`}>{t.status}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, sub, accent = "cyan", testid }) {
  const colors = {
    cyan: "text-cyan-300 bg-cyan-400/10",
    green: "text-emerald-300 bg-emerald-400/10",
    red: "text-red-300 bg-red-400/10",
    purple: "text-violet-300 bg-violet-400/10",
  };
  return (
    <div className="card-surface p-5 animate-fade-up" data-testid={testid}>
      <div className={`w-9 h-9 rounded-md flex items-center justify-center ${colors[accent]}`}>
        <Icon size={17} />
      </div>
      <div className="mt-4 text-xs uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className="text-2xl font-semibold font-mono mt-1">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
    </div>
  );
}
