import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bot, Send, User, Sparkles, ArrowRight, MessageSquare } from "lucide-react";
import { post, fmtMoney } from "../api/client";
import type { ChatReply, ServiceBrief } from "../types";

interface Msg {
  from: "user" | "bot";
  text: string;
  suggestions?: ServiceBrief[];
}

const QUICK = [
  "I need a chatbot for customer support",
  "Who builds recommendation engines?",
  "How does payment work?",
  "How do I become a provider?",
];

const WELCOME: Msg = {
  from: "bot",
  text: "Hi! I'm the QORA AI Concierge. Tell me what you want to build or automate — or ask me anything about how QORA works.",
};

export default function Assistant() {
  const [msgs, setMsgs] = useState<Msg[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, busy]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    setMsgs((m) => [...m, { from: "user", text: message }]);
    setInput("");
    setBusy(true);
    try {
      const reply = await post<ChatReply>("/assistant/chat", { message });
      setMsgs((m) => [...m, { from: "bot", text: reply.reply, suggestions: reply.suggestions }]);
    } catch {
      setMsgs((m) => [...m, { from: "bot", text: "Sorry, I hit a connection problem. Please try again." }]);
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(input);
  };

  return (
    <div className="hero-glow">
      <div className="mx-auto flex max-w-4xl flex-col px-4 pt-10 sm:px-6">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-900/50">
            <Bot size={28} className="text-white" />
          </div>
          <h1 className="font-display text-3xl font-bold text-white">QORA AI Concierge</h1>
          <p className="mx-auto mt-2 max-w-xl text-slate-400">
            Describe your need in plain language — I'll match you with the right services on the network.
          </p>
        </div>

        {/* chat box */}
        <div className="glass flex min-h-[420px] flex-1 flex-col rounded-3xl">
          <div className="flex-1 space-y-4 overflow-y-auto p-6" style={{ maxHeight: "55vh" }}>
            {msgs.map((m, i) => (
              <div key={i} className={`flex gap-3 ${m.from === "user" ? "flex-row-reverse" : ""}`}>
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                    m.from === "user" ? "bg-indigo-500/25 text-indigo-300" : "bg-gradient-to-br from-indigo-500 to-violet-600 text-white"
                  }`}
                >
                  {m.from === "user" ? <User size={15} /> : <Bot size={15} />}
                </div>
                <div className={`max-w-[80%] ${m.from === "user" ? "text-right" : ""}`}>
                  <div
                    className={`inline-block rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                      m.from === "user"
                        ? "rounded-tr-md bg-indigo-500/20 text-slate-100"
                        : "rounded-tl-md bg-white/8 text-slate-200"
                    }`}
                  >
                    {m.text}
                  </div>
                  {m.suggestions && m.suggestions.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {m.suggestions.map((s) => (
                        <Link
                          key={s.id}
                          to={`/services/${s.id}`}
                          className="flex items-center gap-3 rounded-2xl border border-indigo-400/25 bg-indigo-500/10 px-4 py-3 text-left transition hover:border-indigo-400/50 hover:bg-indigo-500/20"
                        >
                          <Sparkles size={16} className="shrink-0 text-indigo-300" />
                          <div className="flex-1">
                            <div className="text-sm font-semibold text-white">{s.title}</div>
                            <div className="text-xs text-slate-400">
                              {s.category_name} · {s.delivery_days}d delivery · ★ {s.rating_avg || "new"}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-sm font-bold text-white">{fmtMoney(s.price_cents)}</div>
                          </div>
                          <ArrowRight size={14} className="text-indigo-300" />
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex items-center gap-2.5 pl-11 text-sm text-slate-500">
                <span className="flex gap-1">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:0ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:150ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-400 [animation-delay:300ms]" />
                </span>
                Concierge is thinking…
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* quick chips */}
          <div className="flex flex-wrap gap-2 border-t border-white/5 px-5 pt-4">
            {QUICK.map((q) => (
              <button
                key={q}
                disabled={busy}
                onClick={() => send(q)}
                className="rounded-full border border-white/10 px-3.5 py-1.5 text-xs text-slate-400 transition hover:border-indigo-400/40 hover:text-indigo-300 disabled:opacity-50"
              >
                {q}
              </button>
            ))}
          </div>

          {/* input */}
          <form onSubmit={submit} className="flex gap-2 p-5">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about chatbots, vision, pricing, becoming a provider…"
              className="input"
            />
            <button type="submit" disabled={busy || !input.trim()} className="btn-primary !px-4">
              <Send size={17} />
            </button>
          </form>
        </div>

        <div className="mt-4 flex items-center justify-center gap-1.5 text-xs text-slate-600">
          <MessageSquare size={12} /> Concierge answers are generated by the QORA matching engine
        </div>
      </div>
    </div>
  );
}
