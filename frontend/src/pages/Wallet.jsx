import { useEffect, useState } from "react";
import { api, ROLE_LABELS } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";
import { ArrowDownCircle, ArrowUpCircle, Loader2 } from "lucide-react";

export default function WalletPage() {
  const { user } = useAuth();
  const [balance, setBalance] = useState(0);
  const [ledger, setLedger] = useState([]);
  const [downline, setDownline] = useState([]);
  const [target, setTarget] = useState("");
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState("credit");
  const [busy, setBusy] = useState(false);

  const load = () => {
    api.get("/wallet/balance").then((r) => setBalance(r.data.balance));
    api.get("/wallet/ledger").then((r) => setLedger(r.data));
    if (user.role !== "retailer") {
      api.get("/users").then((r) => setDownline(r.data));
    }
  };
  useEffect(() => { load(); }, [user.role]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/wallet/transfer", { user_id: target, amount: parseFloat(amount), kind });
      toast.success("Wallet updated");
      setAmount("");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-8">
      <div>
        <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">Wallet</div>
        <h1 className="text-3xl font-semibold mt-1" style={{ fontFamily: "Outfit" }}>Your balance & ledger</h1>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="card-elevated p-6 md:col-span-1">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Available Balance</div>
          <div className="mt-3 text-4xl font-semibold font-mono accent-text" data-testid="wallet-balance">₹ {balance.toFixed(2)}</div>
          <div className="text-xs text-slate-500 mt-2">Signed in as {ROLE_LABELS[user.role]}</div>
        </div>

        {user.role !== "retailer" && (
          <form onSubmit={submit} className="card-surface p-6 md:col-span-2 grid md:grid-cols-2 gap-4">
            <div className="md:col-span-2 text-sm text-slate-400">
              {user.role === "admin"
                ? "Credit or debit any user's wallet. Amount is created / destroyed on your instruction."
                : "Transfer funds from your wallet to your downline."}
            </div>
            <label className="block md:col-span-2">
              <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Recipient</span>
              <select data-testid="wallet-target" required value={target} onChange={(e) => setTarget(e.target.value)} className="input-dark mt-2">
                <option value="">Select user</option>
                {downline.filter((u) => u.user_id !== user.user_id).map((u) => (
                  <option key={u.user_id} value={u.user_id}>{u.name} · {ROLE_LABELS[u.role]} · ₹{u.wallet_balance.toFixed(2)}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Amount (₹)</span>
              <input data-testid="wallet-amount" required type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} className="input-dark mt-2" />
            </label>
            {user.role === "admin" && (
              <label className="block">
                <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Action</span>
                <select data-testid="wallet-kind" value={kind} onChange={(e) => setKind(e.target.value)} className="input-dark mt-2">
                  <option value="credit">Credit</option>
                  <option value="debit">Debit</option>
                </select>
              </label>
            )}
            <div className="md:col-span-2 flex justify-end">
              <button data-testid="wallet-submit" disabled={busy} className="btn-primary flex items-center gap-2">
                {busy && <Loader2 size={16} className="animate-spin" />} Confirm
              </button>
            </div>
          </form>
        )}
      </div>

      <div className="card-surface">
        <div className="p-5 border-b border-white/5">
          <h3 className="text-lg font-semibold" style={{ fontFamily: "Outfit" }}>Ledger</h3>
        </div>
        <div className="divide-y divide-white/5">
          {ledger.length === 0 && <div className="p-6 text-slate-500 text-sm">No wallet activity yet.</div>}
          {ledger.map((l) => (
            <div key={l.id} className="flex items-center justify-between px-5 py-3 hover:bg-white/5">
              <div className="flex items-center gap-3">
                {l.amount >= 0
                  ? <ArrowDownCircle className="text-emerald-400" size={18} />
                  : <ArrowUpCircle className="text-red-400" size={18} />}
                <div>
                  <div className="text-sm">{l.note}</div>
                  <div className="text-xs text-slate-500">{new Date(l.created_at).toLocaleString()} · {l.type}</div>
                </div>
              </div>
              <div className={`font-mono font-semibold ${l.amount >= 0 ? "text-emerald-300" : "text-red-300"}`}>
                {l.amount >= 0 ? "+" : ""}₹ {l.amount.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
