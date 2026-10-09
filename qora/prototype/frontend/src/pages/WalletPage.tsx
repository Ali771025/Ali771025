import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Wallet, PlusCircle, ArrowDownLeft, ArrowUpRight, RefreshCcw, CreditCard, Sparkles,
} from "lucide-react";
import { get, post, fmtMoney, fmtDate } from "../api/client";
import type { Wallet as WalletT } from "../types";
import { Spinner, EmptyState, SectionHeader } from "../components/ui";

const PRESETS = [2000, 5000, 10000, 25000];

const TX_META: Record<string, { icon: any; color: string; sign: "in" | "out" }> = {
  topup: { icon: PlusCircle, color: "text-emerald-300 bg-emerald-500/15", sign: "in" },
  earning: { icon: ArrowDownLeft, color: "text-emerald-300 bg-emerald-500/15", sign: "in" },
  refund: { icon: RefreshCcw, color: "text-sky-300 bg-sky-500/15", sign: "in" },
  purchase: { icon: ArrowUpRight, color: "text-rose-300 bg-rose-500/15", sign: "out" },
  payout: { icon: CreditCard, color: "text-amber-300 bg-amber-500/15", sign: "out" },
};

export default function WalletPage() {
  const [wallet, setWallet] = useState<WalletT | null>(null);
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");

  const load = () => get<WalletT>("/wallet").then(setWallet).catch(() => {});
  useEffect(() => {
    load();
  }, []);

  const topUp = async (e: FormEvent) => {
    e.preventDefault();
    const cents = Math.round(Number(amount) * 100);
    if (!cents || cents <= 0) return;
    setBusy(true);
    setError("");
    setDone("");
    try {
      const w = await post<WalletT>("/wallet/topup", { amount_cents: cents });
      setWallet(w);
      setDone(`${fmtMoney(cents)} added to your wallet.`);
      setAmount("");
    } catch (err: any) {
      setError(err.message || "Top-up failed");
    } finally {
      setBusy(false);
    }
  };

  if (!wallet) return <Spinner label="Loading wallet…" />;

  return (
    <div className="mx-auto max-w-5xl px-4 pt-12 sm:px-6">
      <SectionHeader
        kicker="Payments"
        title="Your wallet"
        subtitle="Fund your wallet once and order any service instantly. Cancelled orders are refunded in full."
      />

      <div className="grid gap-6 lg:grid-cols-[1fr,1.2fr]">
        {/* balance + top-up */}
        <div className="space-y-6">
          <div className="relative overflow-hidden rounded-3xl border border-indigo-400/25 bg-gradient-to-br from-indigo-600 via-violet-600 to-indigo-800 p-7 text-white shadow-2xl shadow-indigo-900/40">
            <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
            <div className="relative">
              <div className="flex items-center gap-2 text-sm text-indigo-100">
                <Wallet size={16} /> Available balance
              </div>
              <div className="mt-3 font-display text-5xl font-bold">{fmtMoney(wallet.balance_cents)}</div>
              <div className="mt-6 flex items-center gap-2 text-xs text-indigo-100">
                <Sparkles size={13} /> Protected by QORA escrow-style payments
              </div>
            </div>
          </div>

          <form onSubmit={topUp} className="glass rounded-2xl p-6">
            <h2 className="mb-4 font-display text-lg font-semibold text-white">Top up wallet</h2>
            <div className="mb-3 grid grid-cols-4 gap-2">
              {PRESETS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setAmount(String(p / 100))}
                  className={`rounded-xl border px-2 py-2 text-sm transition ${
                    Number(amount) === p / 100
                      ? "border-indigo-400/60 bg-indigo-500/20 text-indigo-200"
                      : "border-white/10 text-slate-300 hover:border-white/25"
                  }`}
                >
                  ${p / 100}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500">$</span>
                <input
                  type="number"
                  min="1"
                  max="100000"
                  step="1"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="Custom amount"
                  className="input !pl-8"
                />
              </div>
              <button type="submit" disabled={busy || !amount} className="btn-primary">
                <PlusCircle size={17} /> {busy ? "Processing…" : "Top up"}
              </button>
            </div>
            {error && <div className="mt-3 rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">{error}</div>}
            {done && <div className="mt-3 rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">{done}</div>}
            <p className="mt-3 text-xs text-slate-500">
              Test payments — no real charge. In production this connects to Stripe / payment gateway.
            </p>
          </form>
        </div>

        {/* transactions */}
        <div className="glass rounded-2xl p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-display text-lg font-semibold text-white">Transactions</h2>
            <button onClick={load} className="rounded-xl p-2 text-slate-400 transition hover:bg-white/5 hover:text-white" title="Refresh">
              <RefreshCcw size={15} />
            </button>
          </div>
          {wallet.transactions.length === 0 ? (
            <EmptyState
              icon={<CreditCard size={26} />}
              title="No transactions yet"
              subtitle="Top up your wallet or place your first order to see activity here."
              action={<Link to="/services" className="btn-primary !py-2 !text-sm">Explore services</Link>}
            />
          ) : (
            <div className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
              {wallet.transactions.map((tx) => {
                const meta = TX_META[tx.kind] ?? TX_META.purchase;
                const Icon = meta.icon;
                return (
                  <div key={tx.id} className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.03] px-4 py-3">
                    <div className={`rounded-xl p-2 ${meta.color}`}>
                      <Icon size={16} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm text-slate-200">{tx.description}</div>
                      <div className="text-xs text-slate-500">
                        {fmtDate(tx.created_at)} · <span className="capitalize">{tx.kind}</span>
                      </div>
                    </div>
                    <div className={`font-semibold ${tx.amount_cents >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                      {tx.amount_cents >= 0 ? "+" : "−"}
                      {fmtMoney(Math.abs(tx.amount_cents))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
