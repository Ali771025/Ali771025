import { ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { MessageSquare, Compass, Brain, LogOut, Sparkles, ShieldCheck, X, Store, GitFork } from "lucide-react";
import { useAuth } from "./auth";

export function Navbar() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-[#07070f]/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 font-display text-lg font-bold text-white shadow-lg shadow-indigo-900/50">Q</span>
          <span className="font-display text-xl font-bold text-white">QORA</span>
          <span className="ml-1 rounded-full border border-indigo-400/25 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold text-indigo-300">PHASE 4</span>
        </Link>
        {user && (
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={({ isActive }) => `flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-medium ${isActive ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}>
              <MessageSquare size={16} /> Chat
            </NavLink>
            <NavLink to="/explore" className={({ isActive }) => `flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-medium ${isActive ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}>
              <Compass size={16} /> Explore
            </NavLink>
            <NavLink to="/my-qora" className={({ isActive }) => `flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-medium ${isActive ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}>
              <Brain size={16} /> My QORA
            </NavLink>
            <NavLink to="/creator" className={({ isActive }) => `flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-medium ${isActive ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}>
              <Store size={16} /> Create
            </NavLink>
            <NavLink to="/orchestrate" className={({ isActive }) => `flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-medium ${isActive ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}>
              <GitFork size={16} /> Coordinate
            </NavLink>
            <div className="mx-2 flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5">
              <ShieldCheck size={14} className="text-indigo-300" />
              <span className="max-w-[120px] truncate text-sm text-slate-200">{user.email}</span>
            </div>
            <button onClick={() => { logout(); nav("/login"); }} className="rounded-xl p-2 text-slate-400 hover:bg-white/5 hover:text-rose-300" title="Sign out">
              <LogOut size={17} />
            </button>
          </nav>
        )}
      </div>
    </header>
  );
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div className="glass w-full max-w-md rounded-3xl p-7">
        <div className="mb-5 flex items-start justify-between">
          <h3 className="font-display text-xl font-bold text-white">{title}</h3>
          <button onClick={onClose} className="rounded-xl p-1.5 text-slate-400 hover:bg-white/5 hover:text-white"><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-slate-400">
      <Sparkles className="animate-spin text-indigo-400" size={20} /> {label}
    </div>
  );
}

export function PageHeader({ kicker, title, subtitle }: { kicker: string; title: string; subtitle?: string }) {
  return (
    <div className="mb-8">
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-indigo-400">
        <Sparkles size={14} /> {kicker}
      </div>
      <h1 className="font-display text-3xl font-bold text-white">{title}</h1>
      {subtitle && <p className="mt-2 max-w-2xl text-slate-400">{subtitle}</p>}
    </div>
  );
}
