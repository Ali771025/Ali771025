import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bot, Send, User, Sparkles, ShieldCheck, CheckCircle2, AlertTriangle,
  ThumbsUp, Target, RotateCcw, StopCircle, MessageSquare, ArrowRight, Zap,
} from "lucide-react";
import { get, post, Msg, Conversation, SendResult, Suggestion, fmtScore } from "../api";
import { Modal, Spinner } from "../ui";

const QUICK = [
  "Next week I have an English interview for a Product Manager position",
  "Plan my trip next week to Rome",
  "I want to validate my startup idea",
  "How does QORA protect my data?",
];

export default function Chat() {
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [conv, setConv] = useState<Conversation | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<{ service_id: number; context_types: string[]; message: string } | null>(null);
  const [outcomeCard, setOutcomeCard] = useState<{ session_id: number; status: string; score: number } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    get<Conversation[]>("/conversations").then((cs) => {
      setConvos(cs);
      if (cs.length) loadConv(cs[0].id, cs);
    }).catch(() => {});
  }, []);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  const loadConv = async (id: number, cs?: Conversation[]) => {
    const data = await get<{ conversation: Conversation; messages: Msg[] }>(`/conversations/${id}`);
    setConv(data.conversation);
    setMsgs(data.messages);
    if (cs) setConvos(cs);
  };

  const newConv = async () => {
    const c = await post<Conversation>("/conversations");
    setConvos((x) => [c, ...x]);
    setConv(c);
    setMsgs([]);
    setOutcomeCard(null);
  };

  const send = async (text: string) => {
    const content = text.trim();
    if (!content || busy) return;
    setBusy(true);
    setInput("");
    setMsgs((m) => [...m, { id: Date.now(), role: "user", content, created_at: "", content_blocks: {} }]);
    try {
      let c = conv;
      if (!c) { c = await post<Conversation>("/conversations"); setConv(c); setConvos((x) => [c!, ...x]); }
      const r = await post<SendResult>(`/conversations/${c.id}/messages`, { content });
      setMsgs((m) => [...m, r.message]);
      if (r.message.content_blocks.permission_request) {
        setPending({ ...r.message.content_blocks.permission_request, message: content });
      }
      if (r.outcome && r.service_response.ok) {
        setOutcomeCard({ session_id: r.outcome.session_id, status: r.outcome.status, score: r.outcome.score });
      }
    } catch (e: any) {
      setMsgs((m) => [...m, { id: Date.now(), role: "assistant", content: `Something went wrong: ${e.message}`, created_at: "", content_blocks: {} }]);
    } finally {
      setBusy(false);
    }
  };

  const grant = async (mode: string) => {
    if (!pending) return;
    setBusy(true);
    try {
      await post("/permissions/grants", {
        service_id: pending.service_id,
        context_type: pending.context_types[0],
        mode,
      });
      const msg = pending.message;
      setPending(null);
      if (mode !== "DENY") {
        setBusy(false);
        await send(msg);
        return;
      }
      setMsgs((m) => [...m, { id: Date.now(), role: "assistant", content: "Understood — I won't share that context. The service will work without it, or we can continue here directly.", created_at: "", content_blocks: {} }]);
    } finally {
      setBusy(false);
    }
  };

  const confirmOutcome = async (useful: boolean) => {
    if (!outcomeCard) return;
    await post(`/sessions/${outcomeCard.session_id}/outcome/confirm`, { useful, achieved_goal: useful, notes: "" });
    setOutcomeCard(null);
    setMsgs((m) => [...m, { id: Date.now(), role: "assistant", content: useful ? "Thank you! Your confirmation improves this service's reputation on the network. ⭐" : "Thanks for the honesty — I'll suggest better matches next time.", created_at: "", content_blocks: {} }]);
  };

  const recover = async (option: string) => {
    if (!conv) return;
    const r = await post<{ message: Msg }>(`/conversations/${conv.id}/recovery`, { option });
    setMsgs((m) => [...m, r.message]);
  };

  return (
    <div className="mx-auto flex max-w-6xl gap-6 px-4 py-8">
      {/* sidebar */}
      <aside className="hidden w-64 shrink-0 lg:block">
        <button onClick={newConv} className="btn-primary mb-4 w-full !py-2.5">
          <Sparkles size={16} /> New chat
        </button>
        <div className="space-y-1.5">
          {convos.map((c) => (
            <button key={c.id} onClick={() => loadConv(c.id)}
              className={`w-full rounded-xl border px-3.5 py-2.5 text-left text-sm transition ${conv?.id === c.id ? "border-indigo-400/40 bg-indigo-500/15 text-white" : "border-white/5 text-slate-400 hover:bg-white/5"}`}>
              <div className="flex items-center gap-2">
                <MessageSquare size={13} /> Conversation #{c.id}
              </div>
              <div className="mt-1 text-[11px] text-slate-500">{c.recovery_state === "awaiting_permission" ? "awaiting permission" : c.recovery_state}</div>
            </button>
          ))}
        </div>
      </aside>

      {/* chat */}
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="glass flex flex-1 flex-col rounded-3xl">
          <div className="flex-1 space-y-4 overflow-y-auto p-6" style={{ maxHeight: "62vh" }}>
            {msgs.length === 0 && (
              <div className="py-10 text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600">
                  <Bot size={28} className="text-white" />
                </div>
                <h2 className="font-display text-2xl font-bold text-white">What do you want to achieve today?</h2>
                <p className="mx-auto mt-2 max-w-md text-slate-400">
                  Describe your goal in plain language. QORA understands your intent, remembers what
                  matters to you, and routes you to the right AI service — with your permission.
                </p>
                <div className="mx-auto mt-6 grid max-w-lg gap-2">
                  {QUICK.map((q) => (
                    <button key={q} onClick={() => send(q)} className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-left text-sm text-slate-300 transition hover:border-indigo-400/40 hover:bg-indigo-500/10">
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {msgs.map((m) => (
              <div key={m.id} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${m.role === "user" ? "bg-indigo-500/25 text-indigo-300" : "bg-gradient-to-br from-indigo-500 to-violet-600 text-white"}`}>
                  {m.role === "user" ? <User size={15} /> : <Bot size={15} />}
                </div>
                <div className="max-w-[82%]">
                  <div className={`inline-block whitespace-pre-line rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${m.role === "user" ? "rounded-tr-md bg-indigo-500/20 text-slate-100" : "rounded-tl-md bg-white/8 text-slate-200"}`}>
                    {m.content}
                  </div>
                  {m.content_blocks.suggestions && m.content_blocks.suggestions.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {m.content_blocks.suggestions.map((s) => <SuggestCard key={s.service_id} s={s} />)}
                    </div>
                  )}
                  {m.content_blocks.recovery && (
                    <div className="mt-3 rounded-2xl border border-amber-400/25 bg-amber-500/10 p-4">
                      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-300">
                        <AlertTriangle size={15} /> {m.content_blocks.recovery.failure_type.replace(/_/g, " ").toLowerCase()}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button onClick={() => recover("continue_with_qora")} className="btn-primary !px-3 !py-1.5 !text-xs"><MessageSquare size={13} /> Continue with QORA</button>
                        <button onClick={() => recover("try_another_service")} className="btn-ghost !px-3 !py-1.5 !text-xs">Try another service</button>
                        <button onClick={() => recover("retry")} className="btn-ghost !px-3 !py-1.5 !text-xs"><RotateCcw size={13} /> Retry</button>
                        <button onClick={() => recover("stop")} className="btn-ghost !px-3 !py-1.5 !text-xs"><StopCircle size={13} /> Stop</button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex items-center gap-2.5 pl-11 text-sm text-slate-500">
                <span className="flex gap-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:150ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:300ms]" />
                </span>
                QORA is routing your request…
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={(e: FormEvent) => { e.preventDefault(); send(input); }} className="flex gap-2 border-t border-white/5 p-5">
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Describe your goal…" className="input" />
            <button type="submit" disabled={busy || !input.trim()} className="btn-primary !px-4"><Send size={17} /></button>
          </form>
        </div>
        <div className="mt-3 flex items-center justify-center gap-1.5 text-xs text-slate-600">
          <ShieldCheck size={12} className="text-indigo-400" /> Your personal context is shared only with your explicit permission
        </div>
      </section>

      {/* permission modal [PRD] */}
      {pending && (
        <Modal title="Context permission" onClose={() => setPending(null)}>
          <div className="mb-4 rounded-2xl border border-indigo-400/25 bg-indigo-500/10 p-4 text-sm text-slate-200">
            The service requests access to your <b className="text-indigo-300">{pending.context_types.join(", ")}</b> context.
            It is shared <b>only with this service</b>, per your choice below.
          </div>
          <div className="space-y-2">
            {[
              { mode: "ALLOW_ONCE", icon: <Zap size={16} />, title: "Allow once", desc: "Share for this request only" },
              { mode: "ALWAYS_ALLOW", icon: <ShieldCheck size={16} />, title: "Always allow", desc: "Keep sharing with this service" },
              { mode: "DENY", icon: <StopCircle size={16} />, title: "Deny", desc: "Don't share — continue without it" },
            ].map((o) => (
              <button key={o.mode} onClick={() => grant(o.mode)} disabled={busy}
                className="flex w-full items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-left transition hover:border-indigo-400/40 hover:bg-indigo-500/10 disabled:opacity-50">
                <span className="text-indigo-300">{o.icon}</span>
                <div>
                  <div className="text-sm font-semibold text-white">{o.title}</div>
                  <div className="text-xs text-slate-400">{o.desc}</div>
                </div>
              </button>
            ))}
          </div>
        </Modal>
      )}

      {/* outcome confirmation [PRD: not just a like] */}
      {outcomeCard && (
        <Modal title="Did you reach your goal?" onClose={() => setOutcomeCard(null)}>
          <div className="mb-4 flex items-center gap-3 rounded-2xl border border-emerald-400/25 bg-emerald-500/10 p-4">
            <CheckCircle2 className="text-emerald-300" size={22} />
            <div className="text-sm text-slate-200">
              Outcome: <b className="text-emerald-300">{outcomeCard.status}</b> · quality score {fmtScore(outcomeCard.score)}
            </div>
          </div>
          <p className="mb-5 text-sm text-slate-400">
            QORA validates outcomes with real signals — your confirmation shapes service reputation and rewards.
          </p>
          <div className="flex gap-2">
            <button onClick={() => confirmOutcome(true)} className="btn-primary flex-1"><ThumbsUp size={16} /> Yes, useful</button>
            <button onClick={() => confirmOutcome(false)} className="btn-ghost flex-1">Not really</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function SuggestCard({ s }: { s: Suggestion }) {
  return (
    <Link to={`/explore?s=${s.service_id}`} className="flex items-center gap-3 rounded-2xl border border-indigo-400/25 bg-indigo-500/10 px-4 py-3 transition hover:border-indigo-400/50 hover:bg-indigo-500/20">
      <Target size={16} className="shrink-0 text-indigo-300" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-white">{s.title}</div>
        <div className="text-xs text-slate-400">
          match {fmtScore(s.score)} · success {fmtScore(s.outcome.success_rate)} {s.followed && "· in your toolkit ✓"}
        </div>
      </div>
      <ArrowRight size={14} className="text-indigo-300" />
    </Link>
  );
}
