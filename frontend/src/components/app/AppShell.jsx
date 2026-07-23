import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  LayoutDashboard, Wallet, Zap, Receipt, Users, Settings, LogOut, ShieldCheck, Percent, BarChart3, Menu, X,
} from "lucide-react";
import { ROLE_LABELS } from "@/lib/api";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "master_distributor", "distributor", "retailer"] },
  { to: "/recharge", label: "New Recharge", icon: Zap, roles: ["admin", "master_distributor", "distributor", "retailer"] },
  { to: "/wallet", label: "Wallet", icon: Wallet, roles: ["admin", "master_distributor", "distributor", "retailer"] },
  { to: "/transactions", label: "Transactions", icon: Receipt, roles: ["admin", "master_distributor", "distributor", "retailer"] },
  { to: "/users", label: "Network", icon: Users, roles: ["admin", "master_distributor", "distributor"] },
  { to: "/commissions", label: "Commissions", icon: Percent, roles: ["admin"] },
  { to: "/reports", label: "Reports", icon: BarChart3, roles: ["admin", "master_distributor", "distributor", "retailer"] },
  { to: "/settings", label: "Settings", icon: Settings, roles: ["admin", "master_distributor", "distributor", "retailer"] },
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [balance, setBalance] = useState(0);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let mounted = true;
    api.get("/wallet/balance").then((r) => mounted && setBalance(r.data.balance)).catch(() => {});
    const interval = setInterval(() => {
      api.get("/wallet/balance").then((r) => mounted && setBalance(r.data.balance)).catch(() => {});
    }, 8000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  // close drawer on route change
  useEffect(() => { setOpen(false); }, [loc.pathname]);

  const doLogout = () => { logout(); nav("/login"); };
  if (!user) return null;

  const items = NAV.filter((n) => n.roles.includes(user.role));

  return (
    <div className="min-h-screen text-white relative z-10 md:flex">
      {/* Mobile drawer overlay */}
      {open && (
        <button
          data-testid="mobile-drawer-backdrop"
          onClick={() => setOpen(false)}
          className="md:hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          aria-label="Close menu"
        />
      )}

      {/* Sidebar (desktop static, mobile drawer) */}
      <aside
        data-testid="app-sidebar"
        className={`fixed md:sticky top-0 z-50 h-screen w-64 shrink-0 border-r border-white/5 bg-[#0A0E17] flex flex-col transform transition-transform duration-200 ease-out ${open ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`}
      >
        <div className="p-6 flex items-center gap-3 justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-cyan-400 flex items-center justify-center">
              <ShieldCheck size={20} className="text-slate-950" />
            </div>
            <div>
              <div className="font-semibold tracking-tight" style={{ fontFamily: "Outfit" }}>RechargePro</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Multi-Role Suite</div>
            </div>
          </div>
          <button
            data-testid="mobile-drawer-close"
            className="md:hidden text-slate-400 hover:text-white"
            onClick={() => setOpen(false)}
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        </div>
        <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
          {items.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={`nav-${n.to.slice(1)}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive ? "bg-cyan-400/10 text-cyan-300 border border-cyan-400/20" : "text-slate-300 hover:bg-white/5 border border-transparent"
                }`
              }
            >
              <n.icon size={17} />
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="p-4">
          <button
            onClick={doLogout}
            data-testid="logout-btn"
            className="w-full flex items-center gap-2 justify-center px-3 py-2 rounded-lg text-sm border border-white/10 text-slate-300 hover:bg-white/5 transition-colors"
          >
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-16 border-b border-white/5 px-4 md:px-6 flex items-center justify-between glass sticky top-0 z-30">
          <div className="flex items-center gap-3 min-w-0">
            <button
              data-testid="mobile-drawer-open"
              className="md:hidden p-2 -ml-2 text-slate-300 hover:text-white"
              onClick={() => setOpen(true)}
              aria-label="Open menu"
            >
              <Menu size={22} />
            </button>
            <div className="min-w-0">
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500 truncate">
                <span className="hidden sm:inline">Signed in as </span>{ROLE_LABELS[user.role]}
              </div>
              <div className="text-sm font-medium truncate">
                {user.name}
                <span className="hidden md:inline text-slate-400"> · {user.email}</span>
              </div>
            </div>
          </div>
          <div className="text-right shrink-0 pl-3">
            <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Wallet</div>
            <div className="text-base md:text-lg font-semibold font-mono accent-text whitespace-nowrap" data-testid="header-wallet-balance">₹ {balance.toFixed(2)}</div>
          </div>
        </header>
        <section className="flex-1 p-4 sm:p-6 md:p-8 overflow-y-auto">
          <Outlet />
        </section>
      </main>
    </div>
  );
}
