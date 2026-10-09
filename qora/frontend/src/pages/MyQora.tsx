import { useEffect, useState } from "react";
import { Brain, Target, Route, Trash2, Plus, Sparkles, Coins } from "lucide-react";
import { del, get, post, ContextSummary, Memory } from "../api";
import { PageHeader, Spinner, Modal } from "../ui";

export default function MyQora() {
  const [ctx, setCtx] = useState<ContextSummary | null>(null);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [rewards, setRewards] = useState<any>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ subject: "", content: "", kind: "preference" });

  const load = async () => {
    try {
      const [c, m, r] = await Promise.all([get<ContextSummary>("/me/context"), get<Memory[]>("/me/memories"), get<any>("/rewards/me")]);
      setCtx(c);
      setMemories(m);
      setRewards(r);
    } catch { /* ignore */ }
  };
  useEffect(() => { load(); }, []);

  const add = async () => {
    await post("/me/memories", { ...form, sensitivity: "private", share_policy: "ask" });
    setAdding(false);
    setForm({ subject: "", content: "", kind: "preference" });
    load();
  };

  const forget = async (id: number) => {
    await del(`/me/memories/${id}`);
    load();
  };

  if (!ctx) return <Spinner label="Loading your QORA…" />;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <PageHeader
        kicker="Personal QORA"
        title="What QORA knows about you"
        subtitle="Memory, goals and journeys power personalized matching. You control every item — edit it, or make QORA forget it."
      />

      <div className="mb-8 grid gap-4 sm:grid-cols-3">
        <div className="glass rounded-2xl p-5">
          <div className="mb-2 flex items-center gap-2 text-sm text-slate-400"><Brain size={16} className="text-indigo-300" /> Memories</div>
          <div className="font-display text-2xl font-bold text-white">{memories.length}</div>
        </div>
        <div className="glass rounded-2xl p-5">
          <div className="mb-2 flex items-center gap-2 text-sm text-slate-400"><Target size={16} className="text-indigo-300" /> Active goals</div>
          <div className="font-display text-2xl font-bold text-white">{ctx.goals.filter((g) => g.status === "active").length}</div>
        </div>
        <div className="glass rounded-2xl p-5">
          <div className="mb-2 flex items-center gap-2 text-sm text-slate-400"><Coins size={16} className="text-indigo-300" /> Reward units</div>
          <div className="font-display text-2xl font-bold text-white">{rewards?.balance_units ?? 0}</div>
        </div>
      </div>

      {/* memories */}
      <div className="mb-10">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold text-white">Memories</h2>
          <button onClick={() => setAdding(true)} className="btn-primary !py-2 !text-sm"><Plus size={15} /> Add memory</button>
        </div>
        <div className="space-y-2.5">
          {memories.map((m) => (
            <div key={m.id} className="glass flex items-center gap-4 rounded-2xl px-5 py-4">
              <span className="rounded-lg border border-indigo-400/25 bg-indigo-500/10 px-2.5 py-1 text-xs font-medium capitalize text-indigo-300">
                {m.kind.replace(/_/g, " ")}
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-white">{m.subject}</div>
                <div className="truncate text-xs text-slate-400">{m.content}</div>
              </div>
              <span className="rounded-full border border-white/10 px-2.5 py-0.5 text-[10px] text-slate-500">{m.sensitivity}</span>
              <button onClick={() => forget(m.id)} className="rounded-xl border border-white/10 p-2 text-slate-400 transition hover:border-rose-400/40 hover:text-rose-300" title="Right to forget">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
          {memories.length === 0 && <div className="glass rounded-2xl p-6 text-sm text-slate-400">No memories yet — chat with QORA and it will learn what matters to you.</div>}
        </div>
      </div>

      {/* goals & journeys */}
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h2 className="mb-4 font-display text-xl font-semibold text-white">Goals</h2>
          <div className="space-y-2.5">
            {ctx.goals.map((g, i) => (
              <div key={i} className="glass flex items-center gap-3 rounded-2xl px-5 py-4">
                <Target size={16} className="text-indigo-300" />
                <div className="flex-1 text-sm text-white">{g.title}</div>
                <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-0.5 text-xs text-emerald-300">{g.status}</span>
              </div>
            ))}
            {ctx.goals.length === 0 && <div className="glass rounded-2xl p-6 text-sm text-slate-400">No goals yet.</div>}
          </div>
        </div>
        <div>
          <h2 className="mb-4 font-display text-xl font-semibold text-white">Journeys</h2>
          <div className="space-y-2.5">
            {ctx.journeys.map((j, i) => (
              <div key={i} className="glass rounded-2xl px-5 py-4">
                <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-white">
                  <Route size={15} className="text-indigo-300" /> {j.kind.replace(/_/g, " ")}
                </div>
                <div className="text-xs text-slate-400">
                  step: <span className="text-indigo-300">{String(j.state?.step ?? "—")}</span>
                  {j.state?.service ? <> · via {String(j.state.service)}</> : null}
                </div>
              </div>
            ))}
            {ctx.journeys.length === 0 && <div className="glass rounded-2xl p-6 text-sm text-slate-400">Journeys start when you work toward a goal with a service.</div>}
          </div>
        </div>
      </div>

      {adding && (
        <Modal title="Add a memory" onClose={() => setAdding(false)}>
          <div className="space-y-3">
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} className="input cursor-pointer">
              <option value="preference" className="bg-[#12121f]">Preference</option>
              <option value="profile_fact" className="bg-[#12121f]">Profile fact</option>
              <option value="goal" className="bg-[#12121f]">Goal</option>
              <option value="persistent_context" className="bg-[#12121f]">Persistent context</option>
              <option value="temporary_context" className="bg-[#12121f]">Temporary context</option>
            </select>
            <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="input" placeholder="Subject (e.g. Answer style)" />
            <textarea value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} rows={3} className="input resize-none" placeholder="What should QORA remember?" />
            <button onClick={add} disabled={!form.subject || !form.content} className="btn-primary w-full"><Sparkles size={16} /> Remember this</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
