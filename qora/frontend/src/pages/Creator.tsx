import { useEffect, useState } from "react";
import {
  Store, Sparkles, MessageSquare, FileText, FlaskConical, BadgeCheck, Rocket,
  BookOpen, Plus, Check, X, AlertTriangle, ArrowRight, Brain, BarChart3,
} from "lucide-react";
import { get, post, patch, fmtScore } from "../api";
import { PageHeader, Spinner, Modal } from "../ui";
import { useAuth } from "../auth";

const STEPS = [
  { id: "intent", label: "Intent", icon: <Sparkles size={15} /> },
  { id: "interview", label: "Interview", icon: <MessageSquare size={15} /> },
  { id: "spec", label: "Review", icon: <FileText size={15} /> },
  { id: "simulate", label: "Simulate", icon: <FlaskConical size={15} /> },
  { id: "qualify", label: "Qualify", icon: <BadgeCheck size={15} /> },
  { id: "publish", label: "Publish", icon: <Rocket size={15} /> },
];

export default function Creator() {
  const { user, logout } = useAuth();
  const [tab, setTab] = useState<"wizard" | "services" | "knowledge">("wizard");
  const [needRole, setNeedRole] = useState(false);
  const [step, setStep] = useState("intent");
  const [ivId, setIvId] = useState<number | null>(null);
  const [question, setQuestion] = useState<any>(null);
  const [answer, setAnswer] = useState("");
  const [statement, setStatement] = useState("");
  const [spec, setSpec] = useState<any>(null);
  const [sim, setSim] = useState<any>(null);
  const [qual, setQual] = useState<any>(null);
  const [published, setPublished] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [analytics, setAnalytics] = useState<any>(null);
  // knowledge state
  const [cols, setCols] = useState<any[]>([]);
  const [colDetail, setColDetail] = useState<any>(null);
  const [newCol, setNewCol] = useState("");
  const [matName, setMatName] = useState("");
  const [matContent, setMatContent] = useState("");
  const [insights, setInsights] = useState<any[]>([]);

  useEffect(() => {
    if (user && !user.roles.includes("creator")) setNeedRole(true);
  }, [user]);

  useEffect(() => {
    if (tab === "services") get<any>("/creator/analytics/overview").then(setAnalytics).catch(() => {});
    if (tab === "knowledge") {
      get<any>("/knowledge/collections").then((r) => setCols(r.items || [])).catch(() => {});
    }
  }, [tab]);

  const becomeCreator = async () => {
    await post("/me/profile/creator");
    logout();
    window.location.href = "/login";
  };

  const start = async () => {
    setBusy(true); setError("");
    try {
      const r = await post<any>("/creator/interviews", { intent_statement: statement });
      setIvId(r.id);
      setQuestion(r.next_question);
      setStep("interview");
    } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };

  const submitAnswer = async () => {
    if (!ivId || !question) return;
    setBusy(true);
    try {
      const r = await post<any>(`/creator/interviews/${ivId}/answers`, {
        answers: [{ question_id: question.id, text: answer }],
      });
      setAnswer("");
      if (r.interview_complete) {
        setSpec(r.spec_draft);
        setStep("spec");
        setQuestion(null);
      } else {
        setQuestion(r.next_question);
      }
    } finally { setBusy(false); }
  };

  const runSim = async () => {
    if (!ivId) return;
    setBusy(true);
    try {
      const r = await post<any>(`/creator/interviews/${ivId}/simulate`);
      setSim(r);
      setStep("simulate");
    } finally { setBusy(false); }
  };

  const runQualify = async () => {
    if (!ivId) return;
    setBusy(true);
    try {
      const r = await post<any>(`/creator/interviews/${ivId}/qualify`);
      setQual(r);
      setStep("qualify");
    } finally { setBusy(false); }
  };

  const publish = async () => {
    if (!ivId) return;
    setBusy(true);
    try {
      const r = await post<any>(`/creator/interviews/${ivId}/publish`, { visibility: "public" });
      setPublished(r);
      setStep("publish");
      const ins = await get<any>(`/creator/analytics/services/${r.service_id}/insights`).catch(() => ({ items: [] }));
      setInsights(ins.items || []);
    } finally { setBusy(false); }
  };

  const createCol = async () => {
    if (!newCol.trim()) return;
    const c = await post<any>("/knowledge/collections", { name: newCol });
    setCols((x) => [...x, c]);
    setNewCol("");
    openCol(c.id);
  };

  const openCol = async (id: number) => {
    setColDetail(await get<any>(`/knowledge/collections/${id}`));
  };

  const addMaterial = async () => {
    if (!colDetail || !matName || !matContent) return;
    await post(`/knowledge/collections/${colDetail.id}/sources`, { name: matName, content: matContent });
    setMatName(""); setMatContent("");
    openCol(colDetail.id);
  };

  const freezeVersion = async () => {
    if (!colDetail) return;
    await post(`/knowledge/collections/${colDetail.id}/versions`);
    openCol(colDetail.id);
    if (ivId) await patch(`/creator/interviews/${ivId}/spec`, { knowledge_version_id: (await get<any>(`/knowledge/collections/${colDetail.id}`)).versions.at(-1)?.id }).catch(() => {});
  };

  if (needRole)
    return (
      <div className="mx-auto max-w-2xl px-4 py-20 text-center">
        <Store size={40} className="mx-auto mb-4 text-indigo-400" />
        <h1 className="font-display text-2xl font-bold text-white">Become a creator</h1>
        <p className="mt-2 text-slate-400">One account can be both consumer and creator [PRD] — just add the creator role.</p>
        <button onClick={becomeCreator} className="btn-primary mt-6">Add creator role</button>
      </div>
    );

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <PageHeader
        kicker="Creator platform"
        title="Create an AI service — by talking, not configuring"
        subtitle="Describe what people should be able to do. QORA interviews you about the gaps, drafts the specification, stress-tests it with 7 scenarios, and qualifies it for the network. You never see the words prompt, model or RAG."
      />

      <div className="mb-8 flex gap-2">
        {[
          { id: "wizard", label: "Create service", icon: <Sparkles size={15} /> },
          { id: "services", label: "My services", icon: <BarChart3 size={15} /> },
          { id: "knowledge", label: "Training material", icon: <BookOpen size={15} /> },
        ].map((t) => (
          <button key={t.id} onClick={() => setTab(t.id as any)}
            className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition ${tab === t.id ? "border-indigo-400/50 bg-indigo-500/20 text-indigo-200" : "border-white/10 text-slate-400 hover:border-white/25"}`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {tab === "wizard" && (
        <>
          {/* stepper */}
          <div className="mb-8 flex flex-wrap gap-2">
            {STEPS.map((s, i) => {
              const idx = STEPS.findIndex((x) => x.id === step);
              return (
                <div key={s.id} className={`flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-medium ${i <= idx ? "border-indigo-400/50 bg-indigo-500/15 text-indigo-200" : "border-white/10 text-slate-500"}`}>
                  {s.icon} {s.label}
                </div>
              );
            })}
          </div>

          {error && <div className="mb-4 rounded-xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">{error}</div>}

          {/* STEP 1: intent */}
          {step === "intent" && (
            <div className="glass rounded-2xl p-7">
              <h2 className="mb-2 font-display text-xl font-semibold text-white">What should people be able to do?</h2>
              <p className="mb-4 text-sm text-slate-400">One honest sentence is enough — the interview will find the gaps.</p>
              <textarea value={statement} onChange={(e) => setStatement(e.target.value)} rows={3} className="input resize-none"
                placeholder="e.g. I want to help people prepare for job interviews with real practice and honest feedback" />
              <button onClick={start} disabled={busy || statement.length < 5} className="btn-primary mt-4">
                Start the interview <ArrowRight size={16} />
              </button>
            </div>
          )}

          {/* STEP 2: interview */}
          {step === "interview" && question && (
            <div className="glass rounded-2xl p-7">
              <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-400">
                <MessageSquare size={14} /> Gap detected: {question.gap}
              </div>
              <h2 className="mb-4 font-display text-xl font-semibold text-white">{question.text}</h2>
              <textarea value={answer} onChange={(e) => setAnswer(e.target.value)} rows={3} className="input resize-none" placeholder="Your answer…" />
              <button onClick={submitAnswer} disabled={busy || !answer.trim()} className="btn-primary mt-4">
                {busy ? "Thinking…" : "Next"} <ArrowRight size={16} />
              </button>
            </div>
          )}

          {/* STEP 3: spec review */}
          {step === "spec" && spec && (
            <div className="glass rounded-2xl p-7">
              <h2 className="mb-2 font-display text-xl font-semibold text-white">Your service — drafted</h2>
              <p className="mb-5 text-sm text-slate-400">Review the truth and fix what matters. That's all.</p>
              <div className="space-y-3">
                {[
                  ["name", "Name"], ["purpose", "Purpose"], ["audience", "Audience"],
                  ["method", "Method"], ["boundaries", "Boundaries (what it refuses)"],
                ].map(([k, label]) => (
                  <div key={k}>
                    <label className="mb-1 block text-xs font-medium uppercase tracking-wider text-slate-500">{label}</label>
                    <input value={String(spec[k] ?? "")} onChange={(e) => setSpec({ ...spec, [k]: e.target.value })} className="input !py-2" />
                  </div>
                ))}
                <div>
                  <label className="mb-1 block text-xs font-medium uppercase tracking-wider text-slate-500">Outcome (what the user walks away with)</label>
                  <input value={spec.outcome_definition?.text ?? ""} onChange={(e) => setSpec({ ...spec, outcome_definition: { ...(spec.outcome_definition || {}), text: e.target.value } })} className="input !py-2" />
                </div>
                <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
                  Risk classification: <b className={spec.risk_classification === "LOW" ? "text-emerald-300" : "text-amber-300"}>{spec.risk_classification}</b>
                </div>
              </div>
              <div className="mt-5 flex gap-2">
                <button onClick={async () => { if (ivId) { setSpec(await patch(`/creator/interviews/${ivId}/spec`, { name: spec.name, purpose: spec.purpose, audience: spec.audience, method: spec.method, boundaries: spec.boundaries, outcome_definition: spec.outcome_definition })); } setStep("simulate"); }}
                  className="btn-primary">Save & continue to simulation <ArrowRight size={16} /></button>
                <button onClick={runSim} disabled={busy} className="btn-ghost">Run simulation now</button>
              </div>
            </div>
          )}

          {/* STEP 4: simulation */}
          {step === "simulate" && (
            <div className="glass rounded-2xl p-7">
              <h2 className="mb-2 font-display text-xl font-semibold text-white">Reliability simulation</h2>
              <p className="mb-5 text-sm text-slate-400">7 scenario kinds: normal, ambiguous, edge, boundary, unsafe, unsupported, adversarial.</p>
              {!sim ? (
                <button onClick={runSim} disabled={busy} className="btn-primary"><FlaskConical size={16} /> {busy ? "Running…" : "Run the 7 scenarios"}</button>
              ) : (
                <>
                  <div className="mb-5 flex items-center gap-4 rounded-2xl border border-indigo-400/25 bg-indigo-500/10 p-4">
                    <div className="font-display text-3xl font-bold text-white">{fmtScore(sim.summary.avg_score)}</div>
                    <div className="text-sm text-slate-300">average readiness · {sim.summary.cases} cases</div>
                  </div>
                  <div className="space-y-2">
                    {sim.results.map((r: any) => (
                      <div key={r.kind} className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.03] px-4 py-3">
                        <span className={`h-2 w-2 rounded-full ${r.score >= 0.8 ? "bg-emerald-400" : r.score >= 0.5 ? "bg-amber-400" : "bg-rose-400"}`} />
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium text-white capitalize">{r.kind.replace(/_/g, " ")}</div>
                          <div className="truncate text-xs text-slate-500">{r.actual_behavior}</div>
                          {r.failure_reason && <div className="text-xs text-amber-300/80">{r.failure_reason}</div>}
                        </div>
                        <div className="font-semibold text-slate-200">{fmtScore(r.score)}</div>
                      </div>
                    ))}
                  </div>
                  <button onClick={runQualify} disabled={busy} className="btn-primary mt-5">Run qualification <ArrowRight size={16} /></button>
                </>
              )}
            </div>
          )}

          {/* STEP 5: qualification */}
          {step === "qualify" && qual && (
            <div className="glass rounded-2xl p-7">
              <h2 className="mb-2 font-display text-xl font-semibold text-white">Qualification</h2>
              <div className={`mb-5 inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold ${qual.result === "READY_TO_PUBLISH" ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-300" : "border-amber-400/40 bg-amber-500/15 text-amber-300"}`}>
                <BadgeCheck size={16} /> {qual.result.replace(/_/g, " ")}
              </div>
              <div className="mb-5 space-y-2">
                {qual.checks.map((c: any) => (
                  <div key={c.criterion} className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.03] px-4 py-2.5">
                    {c.passed ? <Check size={15} className="text-emerald-300" /> : <X size={15} className="text-amber-300" />}
                    <div className="flex-1 text-sm text-white capitalize">{c.criterion.replace(/_/g, " ")}</div>
                    <div className="text-xs text-slate-500">{c.detail}</div>
                  </div>
                ))}
              </div>
              {qual.duplicates?.length > 0 && (
                <div className="mb-5 rounded-2xl border border-violet-400/25 bg-violet-500/10 p-4">
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-violet-300">
                    <AlertTriangle size={15} /> Differentiation question (not a rejection)
                  </div>
                  {qual.duplicates.map((d: any, i: number) => (
                    <p key={i} className="text-sm text-slate-300">{d.question}</p>
                  ))}
                </div>
              )}
              <button onClick={publish} disabled={busy} className="btn-primary"><Rocket size={16} /> Publish to the network</button>
            </div>
          )}

          {/* STEP 6: published */}
          {step === "publish" && published && (
            <div className="glass rounded-2xl p-7 text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600">
                <Check size={28} className="text-white" />
              </div>
              <h2 className="font-display text-2xl font-bold text-white">
                {published.lifecycle_status === "published" ? "Your service is live!" : "Almost there"}
              </h2>
              <p className="mx-auto mt-2 max-w-md text-slate-400">
                Service #{published.service_id} · lifecycle: {published.lifecycle_status}
                {published.lifecycle_status !== "published" && " — improve the highlighted checks and re-qualify."}
              </p>
              {insights.length > 0 && (
                <div className="mx-auto mt-5 max-w-md space-y-2 text-left">
                  {insights.map((i: any, k: number) => (
                    <div key={k} className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
                      <Brain size={14} className="mr-1.5 inline text-indigo-300" /> {i.summary}
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-6 flex justify-center gap-2">
                <button onClick={() => { setStep("intent"); setIvId(null); setSpec(null); setSim(null); setQual(null); setPublished(null); }} className="btn-ghost">Create another</button>
                <button onClick={() => setTab("services")} className="btn-primary">See analytics</button>
              </div>
            </div>
          )}
        </>
      )}

      {tab === "services" && (
        <div>
          {!analytics ? <Spinner /> : (
            <>
              <div className="mb-6 grid gap-4 sm:grid-cols-4">
                {[
                  ["Services", analytics.totals.services],
                  ["Users", analytics.totals.users],
                  ["Successful sessions", analytics.totals.successful_sessions],
                  ["Useful votes", analytics.totals.useful_votes],
                ].map(([l, v]) => (
                  <div key={String(l)} className="glass rounded-2xl p-5">
                    <div className="text-xs uppercase tracking-wider text-slate-500">{l}</div>
                    <div className="mt-1 font-display text-2xl font-bold text-white">{v as number}</div>
                  </div>
                ))}
              </div>
              <div className="space-y-3">
                {analytics.per_service.map((s: any) => (
                  <div key={s.service_id} className="glass flex items-center gap-4 rounded-2xl px-5 py-4">
                    <div className="flex-1">
                      <div className="font-semibold text-white">{s.name}</div>
                      <div className="text-xs text-slate-500">
                        {s.users_count} users · {s.successful_sessions} successful · {s.returned_users} returned · success {fmtScore(s.success_rate)}
                      </div>
                    </div>
                    <button onClick={async () => setInsights((await get<any>(`/creator/analytics/services/${s.service_id}/insights`)).items || [])} className="btn-ghost !px-3 !py-1.5 !text-xs">
                      <Brain size={13} /> Insights
                    </button>
                  </div>
                ))}
              </div>
              {insights.length > 0 && (
                <div className="mt-6 space-y-2">
                  {insights.map((i: any, k: number) => (
                    <div key={k} className="rounded-xl border border-indigo-400/25 bg-indigo-500/10 px-4 py-3 text-sm text-slate-200">{i.summary}</div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {tab === "knowledge" && (
        <div>
          <p className="mb-4 text-sm text-slate-400">Add your training material — QORA handles everything else behind the scenes.</p>
          <div className="glass mb-6 flex gap-2 rounded-2xl p-4">
            <input value={newCol} onChange={(e) => setNewCol(e.target.value)} className="input" placeholder="New collection name (e.g. My Course Notes)" />
            <button onClick={createCol} className="btn-primary"><Plus size={16} /> Create</button>
          </div>
          <div className="mb-6 flex flex-wrap gap-2">
            {cols.map((c) => (
              <button key={c.id} onClick={() => openCol(c.id)} className={`rounded-xl border px-4 py-2 text-sm ${colDetail?.id === c.id ? "border-indigo-400/50 bg-indigo-500/15 text-indigo-200" : "border-white/10 text-slate-400 hover:border-white/25"}`}>
                <BookOpen size={14} className="mr-1.5 inline" /> {c.name}
              </button>
            ))}
          </div>
          {colDetail && (
            <div className="glass rounded-2xl p-6">
              <h2 className="mb-4 font-display text-lg font-semibold text-white">{colDetail.id} — materials</h2>
              <div className="space-y-2">
                {colDetail.sources.map((s: any) => (
                  <div key={s.id} className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.03] px-4 py-3">
                    <div className="flex-1">
                      <div className="text-sm text-white">{s.name}</div>
                      <div className="text-xs text-slate-500">{s.scan_status} · {s.fresh ? "fresh" : "stale"} · expires {s.expires_at ? new Date(s.expires_at).toLocaleDateString() : "—"}</div>
                    </div>
                    {s.scan_status === "blocked" && <X size={15} className="text-rose-300" />}
                    {s.scan_status === "clean" && <Check size={15} className="text-emerald-300" />}
                  </div>
                ))}
              </div>
              <div className="mt-4 grid gap-2">
                <input value={matName} onChange={(e) => setMatName(e.target.value)} className="input" placeholder="Material name (e.g. star-method.md)" />
                <textarea value={matContent} onChange={(e) => setMatContent(e.target.value)} rows={4} className="input resize-none" placeholder="Paste your training material…" />
                <button onClick={addMaterial} disabled={!matName || !matContent} className="btn-primary w-fit"><Plus size={16} /> Add material</button>
              </div>
              <div className="mt-6 border-t border-white/5 pt-5">
                <div className="mb-2 text-sm text-slate-400">Versions: {colDetail.versions.length}</div>
                <button onClick={freezeVersion} className="btn-ghost !py-2 !text-sm"><BadgeCheck size={15} /> Freeze version & attach to service</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
