import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { UserPlus, User, Store, CheckCircle2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role: "consumer", headline: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const u = await register(form);
      nav(u.role === "provider" ? "/provider" : "/dashboard", { replace: true });
    } catch (err: any) {
      setError(err.message || "Registration failed");
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
              <UserPlus size={22} className="text-white" />
            </div>
            <h1 className="font-display text-2xl font-bold text-white">Create your account</h1>
            <p className="mt-1.5 text-sm text-slate-400">Join the QORA AI service network</p>
          </div>

          <div className="mb-5 grid grid-cols-2 gap-2">
            {[
              { id: "consumer", label: "I want to buy", icon: <User size={16} />, desc: "Order AI services" },
              { id: "provider", label: "I want to sell", icon: <Store size={16} />, desc: "Publish AI services" },
            ].map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => set("role", r.id)}
                className={`rounded-2xl border p-4 text-left transition ${
                  form.role === r.id
                    ? "border-indigo-400/60 bg-indigo-500/15"
                    : "border-white/10 bg-white/5 hover:border-white/25"
                }`}
              >
                <div className="mb-1.5 flex items-center gap-2 text-sm font-semibold text-white">
                  {r.icon} {r.label}
                  {form.role === r.id && <CheckCircle2 size={14} className="ml-auto text-indigo-400" />}
                </div>
                <div className="text-xs text-slate-400">{r.desc}</div>
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-300">Full name</label>
              <input required minLength={2} value={form.full_name} onChange={(e) => set("full_name", e.target.value)} className="input" placeholder="Ada Lovelace" />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-300">Email</label>
              <input type="email" required value={form.email} onChange={(e) => set("email", e.target.value)} className="input" placeholder="you@company.com" />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-slate-300">Password</label>
              <input type="password" required minLength={6} value={form.password} onChange={(e) => set("password", e.target.value)} className="input" placeholder="At least 6 characters" />
            </div>
            {form.role === "provider" && (
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-300">Professional headline</label>
                <input value={form.headline} onChange={(e) => set("headline", e.target.value)} className="input" placeholder="Senior AI Engineer · NLP & RAG systems" maxLength={200} />
              </div>
            )}
            {error && <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-300">{error}</div>}
            <button type="submit" disabled={busy} className="btn-primary w-full !py-3">
              {busy ? "Creating account…" : "Create account"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-400">
            Already have an account?{" "}
            <Link to="/login" className="font-semibold text-indigo-400 hover:text-indigo-300">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
