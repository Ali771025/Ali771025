import { Link, NavLink, useNavigate } from "react-router-dom";
import { Sparkles, LayoutGrid, MessageSquare, Wallet, LogOut, Menu, X, Bot, Store, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { Avatar } from "./ui";

const links = [
  { to: "/services", label: "Explore", icon: <LayoutGrid size={16} /> },
  { to: "/assistant", label: "AI Concierge", icon: <Bot size={16} /> },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);

  const dashboardLink =
    user?.role === "admin"
      ? { to: "/admin", label: "Admin", icon: <ShieldCheck size={16} /> }
      : user?.role === "provider"
        ? { to: "/provider", label: "Provider", icon: <Store size={16} /> }
        : user
          ? { to: "/dashboard", label: "Dashboard", icon: <LayoutGrid size={16} /> }
          : null;

  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-[#07070f]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 font-display text-lg font-bold text-white shadow-lg shadow-indigo-900/50">
            Q
          </span>
          <span className="font-display text-xl font-bold tracking-tight text-white">
            QORA
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) =>
                `flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-medium transition ${
                  isActive ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              {l.icon} {l.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          {user ? (
            <>
              <Link to="/wallet" className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/5 hover:text-white">
                <Wallet size={16} /> Wallet
              </Link>
              {dashboardLink && (
                <Link to={dashboardLink.to} className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/5 hover:text-white">
                  {dashboardLink.icon} {dashboardLink.label}
                </Link>
              )}
              <div className="ml-1 flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 py-1.5 pl-1.5 pr-3">
                <Avatar user={user} size={28} />
                <span className="max-w-[110px] truncate text-sm font-medium text-slate-200">{user.full_name}</span>
              </div>
              <button
                onClick={() => {
                  logout();
                  nav("/");
                }}
                className="rounded-xl p-2 text-slate-400 transition hover:bg-white/5 hover:text-rose-300"
                title="Sign out"
              >
                <LogOut size={17} />
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="rounded-xl px-4 py-2 text-sm font-medium text-slate-300 transition hover:bg-white/5 hover:text-white">
                Sign in
              </Link>
              <Link to="/register" className="btn-primary !py-2 !text-sm">
                Get started
              </Link>
            </>
          )}
        </div>

        <button className="rounded-xl p-2 text-slate-300 md:hidden" onClick={() => setOpen(!open)}>
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {open && (
        <div className="border-t border-white/5 px-4 py-3 md:hidden">
          <div className="flex flex-col gap-1">
            {[...links, ...(dashboardLink ? [dashboardLink] : []), { to: "/wallet", label: "Wallet", icon: <Wallet size={16} /> }].map((l) => (
              <Link key={l.to} to={l.to} onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-slate-300 hover:bg-white/5">
                {l.icon} {l.label}
              </Link>
            ))}
            {user ? (
              <button
                onClick={() => {
                  logout();
                  setOpen(false);
                  nav("/");
                }}
                className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-rose-300 hover:bg-white/5"
              >
                <LogOut size={16} /> Sign out
              </button>
            ) : (
              <div className="mt-2 flex gap-2">
                <Link to="/login" onClick={() => setOpen(false)} className="btn-ghost flex-1 !py-2 !text-sm">Sign in</Link>
                <Link to="/register" onClick={() => setOpen(false)} className="btn-primary flex-1 !py-2 !text-sm">Get started</Link>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
