import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { LogIn, Sparkles, Bot, ShieldCheck, User, Store } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const DEMOS = [
  { email: "omar@qora.ai", password: "consumer123", label: "Consumer", icon: <User size={15} />, desc: "browse & order" },
  { email: "sarah@qora.ai", password: "provider123", label: "Provider", icon: <Store size={15} />, desc: "sell AI services" },
  { email: "admin@qora.ai", password: "admin123", label: "Admin", icon: <ShieldCheck size={15} />, desc: "manage platform" },
];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as any;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const go = (role: string) => {
    const from = loc.state?.from;
    nav(from || (role === "admin" ? "/admin" : role === "provider" ? "/provider" : "/dashboard"), { replace: true });
  };

  const submit = async (e: FormEvent, creds?: { email: string; password: string }) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const u = await login(creds?.email ?? email, creds?.password ?? password);
      go(u.role);
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="hero-glow flex min-h-[80vh] items-center justify-center px-4 py-16">
      <div className="w-full max-w-md">
        <div className="glass fade-up rounded-3xl p-8">
          <div className="mb-6 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600">
              <Sparkles size={22} className="text-white" />
            </div>
            <h1 className="font-display text-2xl font-bold text-white">Welcome back</h1>
            <p className="mt-1.5 text-sm text-slate-400">Sign in to your QORA account</p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-300">Email</label>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="input" placeholder="you@company.com" />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-300">Password</label>
              <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="input" placeholder="••••••••" />
            </div>
            {error && <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-300">{error}</div>}
            <button type="submit" disabled={busy} className="btn-primary w-full !py-3">
              <LogIn size={17} /> {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <div className="mt-6">
            <div className="mb-3 text-center text-xs uppercase tracking-wider text-slate-500">Quick demo access</div>
            <div className="grid grid-cols-3 gap-2">
              {DEMOS.map((d) => (
                <button
                  key={d.email}
                  disabled={busy}
                  onClick={(e) => submit(e as any, d)}
                  className="rounded-xl border border-white/10 bg-white/5 px-2 py-3 text-center transition hover:border-indigo-400/40 hover:bg-indigo-500/10 disabled:opacity-50"
                >
                  <div className="mb-1 flex justify-center text-indigo-300">{d.icon}</div>
                  <div className="text-xs font-semibold text-white">{d.label}</div>
                  <div className="text-[10px] text-slate-500">{d.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <p className="mt-6 text-center text-sm text-slate-400">
            New to QORA?{" "}
            <Link to="/register" className="font-semibold text-indigo-400 hover:text-indigo-300">
              Create an account
            </Link>
          </p>
        </div>

        <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-500">
          <Bot size={14} className="text-indigo-400" />
          Tip: the AI Concierge works without an account
        </div>
      </div>
    </div>
  );
}
