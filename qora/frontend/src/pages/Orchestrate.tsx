import { useEffect, useState } from "react";
import { ArrowRight, Check, GitFork, LoaderCircle, Play, Sparkles, X } from "lucide-react";
import { get, post } from "../api";
import { PageHeader, Spinner } from "../ui";

type PlanStep = {
  id: number;
  order: number;
  service_id: number;
  service_name: string;
  role: string;
  status: "pending" | "done" | "failed" | "skipped";
  score: number;
  session_id: number | null;
  output: { content?: string; hint?: string; reason?: string; failure?: any };
};

type Plan = {
  id: number;
  goal_text: string;
  intent_slug: string;
  status: "draft" | "running" | "completed" | "partial" | "failed";
  summary: string;
  steps: PlanStep[];
};

const statusTone: Record<string, string> = {
  draft: "border-indigo-400/30 bg-indigo-500/10 text-indigo-200",
  running: "border-amber-400/30 bg-amber-500/10 text-amber-200",
  completed: "border-emerald-400/30 bg-emerald-500/10 text-emerald-200",
  partial: "border-amber-400/30 bg-amber-500/10 text-amber-200",
  failed: "border-rose-400/30 bg-rose-500/10 text-rose-200",
};

export default function Orchestrate() {
  const [goal, setGoal] = useState("");
  const [plans, setPlans] = useState<Plan[]>([]);
  const [active, setActive] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadPlans = async () => {
    try {
      const response = await get<{ items: Plan[] }>("/orchestration/plans");
      setPlans(response.items || []);
    } catch {
      setPlans([]);
    }
  };

  useEffect(() => { void loadPlans(); }, []);

  const makePlan = async () => {
    if (goal.trim().length < 3) return;
    setBusy(true); setError("");
    try {
      const result = await post<Plan>("/orchestration/plans", { goal_text: goal.trim() });
      setActive(result);
      setGoal("");
      await loadPlans();
    } catch (e: any) { setError(e.message || "QORA could not find a safe service chain for that goal."); }
    finally { setBusy(false); }
  };

  const execute = async (plan: Plan) => {
    setBusy(true); setError("");
    try {
      const result = await post<Plan>(`/orchestration/plans/${plan.id}/execute`);
      setActive(result);
      await loadPlans();
    } catch (e: any) { setError(e.message || "The plan could not be completed."); }
    finally { setBusy(false); }
  };

  const openPlan = async (id: number) => {
    setActive(await get<Plan>(`/orchestration/plans/${id}`));
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <PageHeader
        kicker="One goal, coordinated help"
        title="Let QORA coordinate the work"
        subtitle="Describe an outcome that needs more than one kind of help. QORA will show you the steps first, then carry results forward between specialists."
      />

      <div className="glass rounded-2xl p-6">
        <label htmlFor="orchestration-goal" className="mb-2 block font-display text-lg font-semibold text-white">
          What would you like to accomplish?
        </label>
        <textarea
          id="orchestration-goal"
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
          rows={3}
          maxLength={2000}
          className="input resize-none"
          placeholder="For example: prepare for my interview and polish the resume I will send beforehand"
        />
        {error && <div className="mt-3 rounded-xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">{error}</div>}
        <button onClick={makePlan} disabled={busy || goal.trim().length < 3} className="btn-primary mt-4">
          {busy ? <LoaderCircle size={16} className="animate-spin" /> : <Sparkles size={16} />}
          Build my plan <ArrowRight size={16} />
        </button>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <section className="space-y-4">
          {active ? (
            <div className="glass rounded-2xl p-6">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-indigo-300">Your plan</div>
                  <h2 className="mt-1 font-display text-xl font-semibold text-white">{active.goal_text}</h2>
                </div>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold capitalize ${statusTone[active.status] || statusTone.draft}`}>
                  {active.status}
                </span>
              </div>
              <p className="mb-5 text-sm text-slate-400">{active.summary}</p>
              <div className="space-y-3">
                {active.steps.map((step, index) => (
                  <div key={step.id} className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                    <div className="flex items-start gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-500/15 text-sm font-bold text-indigo-200">
                        {step.status === "done" ? <Check size={15} /> : step.status === "failed" ? <X size={15} /> : index + 1}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-semibold text-white">{step.service_name}</h3>
                          <span className="rounded-full border border-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                            {step.role.replace(/_/g, " ")}
                          </span>
                          <span className="text-xs capitalize text-slate-500">{step.status}</span>
                        </div>
                        {step.output?.content && <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-300">{step.output.content}</p>}
                        {!step.output?.content && step.output?.hint && active.status === "draft" && <p className="mt-2 text-sm text-slate-400">{step.output.hint}</p>}
                        {step.output?.reason && <p className="mt-2 text-sm text-amber-300">{step.output.reason}</p>}
                        {step.output?.failure?.detail && <p className="mt-2 text-sm text-rose-300">{step.output.failure.detail}</p>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {active.status === "draft" && (
                <button onClick={() => execute(active)} disabled={busy} className="btn-primary mt-5">
                  {busy ? <LoaderCircle size={16} className="animate-spin" /> : <Play size={15} />}
                  Run these steps
                </button>
              )}
            </div>
          ) : (
            <div className="glass rounded-2xl px-6 py-10 text-center text-sm text-slate-400">
              <GitFork size={25} className="mx-auto mb-3 text-indigo-300" />
              Your plan and combined results will appear here.
            </div>
          )}
        </section>

        <aside className="glass h-fit rounded-2xl p-5">
          <h2 className="mb-3 font-display text-lg font-semibold text-white">Recent plans</h2>
          {plans.length === 0 ? <p className="text-sm text-slate-500">Your plans will be saved here.</p> : (
            <div className="space-y-2">
              {plans.map((plan) => (
                <button key={plan.id} onClick={() => void openPlan(plan.id)}
                  className={`w-full rounded-xl border p-3 text-left transition ${active?.id === plan.id ? "border-indigo-400/40 bg-indigo-500/10" : "border-white/5 bg-white/[0.02] hover:border-white/15"}`}>
                  <span className="block line-clamp-2 text-sm font-medium text-slate-200">{plan.goal_text}</span>
                  <span className="mt-1 block text-xs capitalize text-slate-500">{plan.status} · {plan.steps?.length || 0} steps</span>
                </button>
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
