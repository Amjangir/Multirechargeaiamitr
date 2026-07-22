import { Link } from "react-router-dom";
import { ArrowRight, ShieldCheck, Zap, Wallet, Users, BarChart3, Sparkles, TrendingUp } from "lucide-react";

export default function Landing() {
  return (
    <div className="relative z-10 min-h-screen">
      {/* Nav */}
      <nav className="glass sticky top-0 z-20">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-md accent-bg flex items-center justify-center">
              <ShieldCheck size={18} />
            </div>
            <span className="font-semibold tracking-tight text-lg" style={{ fontFamily: "Outfit" }}>RechargePro</span>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" data-testid="nav-login-link" className="btn-ghost text-sm">Sign in</Link>
            <Link to="/signup" data-testid="nav-signup-link" className="btn-primary text-sm">Get Started <ArrowRight size={16} className="inline ml-1" /></Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 pt-20 pb-24 grid md:grid-cols-12 gap-10">
        <div className="md:col-span-7 animate-fade-up">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-cyan-400/30 bg-cyan-400/5 text-cyan-300 text-xs uppercase tracking-[0.2em]">
            <Sparkles size={13} /> Fintech-grade recharge platform
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-none mt-6" style={{ fontFamily: "Outfit" }}>
            Run a <span className="accent-text">multi-role</span><br />
            recharge empire —<br />
            without the chaos.
          </h1>
          <p className="mt-6 text-slate-300 text-base leading-relaxed max-w-xl">
            RechargePro powers Admins, Master Distributors, Distributors and Retailers with a single wallet-driven engine.
            Mobile, DTH, Electricity, Data Card — all from a lightning-fast dark cockpit.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/signup" data-testid="hero-cta-signup" className="btn-primary">Start free trial <ArrowRight size={16} className="inline ml-1" /></Link>
            <Link to="/login" data-testid="hero-cta-login" className="btn-ghost">Sign in to console</Link>
          </div>
          <div className="mt-10 grid grid-cols-3 gap-6 max-w-md">
            <Stat k="4" v="Roles" />
            <Stat k="4" v="Services" />
            <Stat k="99.9%" v="Uptime" />
          </div>
        </div>

        <div className="md:col-span-5 relative animate-fade-up" style={{ animationDelay: "120ms" }}>
          <div className="card-elevated p-6 relative overflow-hidden">
            <img
              src="https://images.unsplash.com/photo-1618058313199-9037610ec161?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzR8MHwxfHNlYXJjaHwyfHxtb2Rlcm4lMjBmaW50ZWNoJTIwYWJzdHJhY3QlMjB0cmFuc2FjdGlvbnxlbnwwfHx8fDE3ODQ3MjcxNzJ8MA&ixlib=rb-4.1.0&q=85"
              alt="Fintech visual"
              className="w-full h-56 object-cover rounded-lg opacity-70"
            />
            <div className="absolute inset-6 flex flex-col justify-end">
              <div className="glass rounded-lg p-4 mb-4">
                <div className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Live wallet</div>
                <div className="text-3xl font-mono accent-text">₹ 84,210.55</div>
                <div className="text-xs text-slate-400 mt-1">+ 12 recharges in the last hour</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Bento features */}
      <section className="max-w-7xl mx-auto px-6 pb-24">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          <Card className="md:col-span-7" title="One wallet, four roles" icon={Wallet} desc="Admins fund the ecosystem. Master Distributors and Distributors move funds down the chain. Retailers spend, earn commissions, and never see a bank." />
          <Card className="md:col-span-5" title="All utilities, one form" icon={Zap} desc="Mobile Prepaid, DTH, Electricity, Data Card — each with operators, circles, and a 90%+ mock success rate to demo instantly." />
          <Card className="md:col-span-5" title="RBAC that just works" icon={ShieldCheck} desc="Role-based dashboards, downline scoping, and hardened JWT auth. Nobody sees anything they shouldn't." />
          <Card className="md:col-span-7" title="Reports that respect scope" icon={BarChart3} desc="Every metric — daily volume, success ratio, commissions — is scoped to your role's downline. Admins see all, retailers see themselves." />
        </div>
      </section>

      {/* Roles */}
      <section className="max-w-7xl mx-auto px-6 pb-24">
        <div className="mb-10">
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-300">Built for hierarchy</div>
          <h2 className="text-3xl sm:text-4xl font-semibold mt-2" style={{ fontFamily: "Outfit" }}>A dashboard for every seat at the table</h2>
        </div>
        <div className="grid md:grid-cols-4 gap-4">
          {[
            { r: "Admin", t: "Own the platform", d: "Approve users, credit wallets, oversee every transaction, tune commissions.", i: ShieldCheck },
            { r: "Master Distributor", t: "Command the region", d: "Onboard distributors, fund downlines, watch aggregate commissions.", i: TrendingUp },
            { r: "Distributor", t: "Grow your retailers", d: "Recruit shops, top-up their wallets, oversee daily sales.", i: Users },
            { r: "Retailer", t: "Sell in seconds", d: "Recharge any service in under 10 seconds. Track earnings live.", i: Zap },
          ].map((x, i) => (
            <div key={x.r} className="card-surface p-6 animate-fade-up" style={{ animationDelay: `${i * 80}ms` }}>
              <div className="w-10 h-10 rounded-md bg-cyan-400/10 text-cyan-300 flex items-center justify-center mb-4">
                <x.i size={18} />
              </div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">{x.r}</div>
              <div className="text-lg font-semibold mt-1">{x.t}</div>
              <p className="text-sm text-slate-400 mt-3 leading-relaxed">{x.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-5xl mx-auto px-6 pb-24">
        <div className="card-elevated p-10 md:p-14 relative overflow-hidden">
          <div className="relative z-10">
            <h2 className="text-3xl sm:text-4xl font-semibold" style={{ fontFamily: "Outfit" }}>
              Ready to <span className="accent-text">recharge</span> your business?
            </h2>
            <p className="text-slate-300 mt-3 max-w-xl">Spin up your operator in less than a minute. No card required. Mock recharges enabled for instant demo.</p>
            <div className="mt-6 flex gap-3">
              <Link to="/signup" data-testid="cta-bottom-signup" className="btn-primary">Create account</Link>
              <Link to="/login" data-testid="cta-bottom-login" className="btn-ghost">I already have one</Link>
            </div>
          </div>
          <div className="absolute -right-16 -bottom-16 w-64 h-64 rounded-full bg-cyan-400/20 blur-3xl" />
        </div>
      </section>

      <footer className="border-t border-white/5 py-8 text-center text-xs text-slate-500">
        © RechargePro · Built for demo purposes · Mock recharges only
      </footer>
    </div>
  );
}

function Stat({ k, v }) {
  return (
    <div>
      <div className="text-2xl font-semibold" style={{ fontFamily: "Outfit" }}>{k}</div>
      <div className="text-xs uppercase tracking-[0.2em] text-slate-500 mt-1">{v}</div>
    </div>
  );
}

function Card({ className = "", title, desc, icon: Icon }) {
  return (
    <div className={`card-surface p-8 ${className} animate-fade-up`}>
      <div className="w-10 h-10 rounded-md bg-cyan-400/10 text-cyan-300 flex items-center justify-center mb-5">
        <Icon size={18} />
      </div>
      <h3 className="text-xl font-semibold" style={{ fontFamily: "Outfit" }}>{title}</h3>
      <p className="text-sm text-slate-400 mt-3 leading-relaxed">{desc}</p>
    </div>
  );
}
