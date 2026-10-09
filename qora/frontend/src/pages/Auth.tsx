import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { LogIn, UserPlus, Sparkles, Bot, ShieldCheck } from "lucide-react";
import { useAuth } from "../auth";

export default function Auth({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as any;
  const [form, setForm] = useState({ email: "", password: "", display_name: "", role: "consumer" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "login") await login(form.email, form.password);
      else await register({ email: form.email, password: form.password, display_name: form.display_name, roles_wanted: [form.role] });
      nav(loc.state?.from || "/", { replace: true });
    } catch (err: any) {
      setError(err.message || "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="hero-glow flex min-h-[85vh] items-center justify-center px-4 py-16">
      <div className="w-full max-w-md">
        <div className="glass fade-up rounded-3xl p-8">
          <div className="mb-6 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600">
              <Sparkles size={22} className="text-white" />
            </div>
            <h1 className="font-display text-2xl font-bold text-white">{mode === "login" ? "Welcome back" : "Join QORA"}</h1>
            <p className="mt-1.5 text-sm text-slate-400">
              {mode === "login" ? "Your personal AI network is waiting" : "One account — consumer and creator in one [PRD]"}
            </p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            {mode === "register" && (
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-300">Full name</label>
                <input required minLength={2} value={form.display_name} onChange={(e) => set("display_name", e.target.value)} className="input" placeholder="Ada Lovelace" />
              </div>
            )}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-300">Email</label>
              <input type="email" required value={form.email} onChange={(e) => set("email", e.target.value)} className="input" placeholder="you@example.com" />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-300">Password</label>
              <input type="password" required minLength={6} value={form.password} onChange={(e) => set("password", e.target.value)} className="input" placeholder="At least 6 characters" />
            </div>
            {mode === "register" && (
              <div className="grid grid-cols-2 gap-2">
                {[{ id: "consumer", label: "I want to use AI services" }, { id: "creator", label: "I want to create services" }].map((r) => (
                  <button key={r.id} type="button" onClick={() => set("role", r.id)}
                    className={`rounded-2xl border p-3 text-left text-xs font-medium transition ${form.role === r.id ? "border-indigo-400/60 bg-indigo-500/15 text-white" : "border-white/10 bg-white/5 text-slate-400 hover:border-white/25"}`}>
                    {r.label}
                  </button>
                ))}
              </div>
            )}
            {error && <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-300">{error}</div>}
            <button type="submit" disabled={busy} className="btn-primary w-full !py-3">
              {mode === "login" ? <><LogIn size={17} /> Sign in</> : <><UserPlus size={17} /> Create account</>}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-400">
            {mode === "login" ? (
              <>New to QORA? <button onClick={() => nav("/register")} className="font-semibold text-indigo-400 hover:text-indigo-300">Create an account</button></>
            ) : (
              <>Already have an account? <button onClick={() => nav("/login")} className="font-semibold text-indigo-400 hover:text-indigo-300">Sign in</button></>
            )}
          </p>

          {mode === "login" && (
            <div className="mt-5 rounded-2xl border border-white/10 bg-white/5 p-3.5 text-xs text-slate-400">
              <div className="mb-1.5 font-semibold text-slate-300">Demo accounts</div>
              <div>Consumer: <code className="text-indigo-300">emma@qora.ai / consumer123</code></div>
              <div>Creator: <code className="text-indigo-300">sarah@qora.ai / provider123</code></div>
            </div>
          )}
        </div>

        <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-500">
          <ShieldCheck size={14} className="text-indigo-400" /> Least-context privacy by design <Bot size={14} className="ml-3 text-indigo-400" /> Personal AI + Service Network
        </div>
      </div>
    </div>
  );
}
