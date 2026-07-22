import { useEffect, useState } from "react";
import { api, SERVICES } from "@/lib/api";
import { toast } from "sonner";
import { Smartphone, Tv, Zap, Wifi, Loader2, CheckCircle2, XCircle } from "lucide-react";

const ICON = { Smartphone, Tv, Zap, Wifi };

export default function Recharge() {
  const [service, setService] = useState("mobile_prepaid");
  const [operators, setOperators] = useState({});
  const [operator, setOperator] = useState("");
  const [number, setNumber] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    api.get("/operators").then((r) => {
      setOperators(r.data);
      setOperator(r.data[service][0].code);
    });
  }, []);

  useEffect(() => {
    if (operators[service]) setOperator(operators[service][0].code);
  }, [service, operators]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setResult(null);
    try {
      const { data } = await api.post("/recharge", {
        service, operator, number, amount: parseFloat(amount),
      });
      setResult(data);
      if (data.status === "success") toast.success(`Recharge success · Ref ${data.operator_ref}`);
      else toast.error("Recharge failed. No amount deducted.");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Recharge error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-4xl">
      <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">New Recharge</div>
      <h1 className="text-3xl font-semibold mt-1 mb-8" style={{ fontFamily: "Outfit" }}>What do you want to top-up?</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        {SERVICES.map((s) => {
          const Ic = ICON[s.icon];
          const active = service === s.code;
          return (
            <button
              key={s.code}
              type="button"
              data-testid={`service-${s.code}`}
              onClick={() => setService(s.code)}
              className={`card-surface p-5 text-left transition-colors border ${active ? "border-cyan-400/40 bg-cyan-400/5" : "border-transparent hover:bg-white/5"}`}
            >
              <Ic size={22} className={active ? "text-cyan-300" : "text-slate-400"} />
              <div className="mt-3 font-medium">{s.name}</div>
            </button>
          );
        })}
      </div>

      <form onSubmit={submit} className="card-elevated p-8 grid md:grid-cols-2 gap-6">
        <label className="block md:col-span-2">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Operator</span>
          <select data-testid="recharge-operator" value={operator} onChange={(e) => setOperator(e.target.value)} className="input-dark mt-2">
            {(operators[service] || []).map((o) => (<option key={o.code} value={o.code}>{o.name}</option>))}
          </select>
        </label>
        <label className="block">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
            {service === "mobile_prepaid" ? "Mobile Number" : service === "dth" ? "Subscriber ID" : service === "electricity" ? "Consumer No." : "Account ID"}
          </span>
          <input data-testid="recharge-number" required value={number} onChange={(e) => setNumber(e.target.value)} className="input-dark mt-2" placeholder="Enter number" />
        </label>
        <label className="block">
          <span className="text-xs uppercase tracking-[0.2em] text-slate-500">Amount (₹)</span>
          <input data-testid="recharge-amount" required type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} className="input-dark mt-2" placeholder="299" />
        </label>
        <div className="md:col-span-2 flex items-center justify-between mt-4">
          <div className="text-xs text-slate-500">
            Mock gateway · ~90% success rate · 2% commission on success.
          </div>
          <button data-testid="recharge-submit" disabled={busy} className="btn-primary flex items-center gap-2">
            {busy && <Loader2 size={16} className="animate-spin" />} Process recharge
          </button>
        </div>
      </form>

      {result && (
        <div className={`mt-6 card-surface p-6 border ${result.status === "success" ? "border-emerald-400/30" : "border-red-400/30"}`} data-testid="recharge-result">
          <div className="flex items-center gap-3">
            {result.status === "success" ? <CheckCircle2 className="text-emerald-400" /> : <XCircle className="text-red-400" />}
            <div>
              <div className="font-semibold text-lg">{result.status === "success" ? "Recharge Successful" : "Recharge Failed"}</div>
              <div className="text-sm text-slate-400">Ref: <span className="font-mono">{result.operator_ref}</span></div>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <Kv k="Service" v={result.service.replace("_", " ")} />
            <Kv k="Number" v={result.number} />
            <Kv k="Amount" v={`₹ ${result.amount.toFixed(2)}`} />
            <Kv k="Commission" v={`₹ ${(result.commission || 0).toFixed(2)}`} />
          </div>
        </div>
      )}
    </div>
  );
}

function Kv({ k, v }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{k}</div>
      <div className="mt-1 font-medium">{v}</div>
    </div>
  );
}
