import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Clock, Tag, Star, ShieldCheck, ArrowLeft, Wallet, CheckCircle2, MessageSquare, Sparkles,
} from "lucide-react";
import { get, post, fmtMoney, fmtDate } from "../api/client";
import type { Order, Review, Service } from "../types";
import { Avatar, Stars, StatusBadge, Spinner, EmptyState } from "../components/ui";
import { useAuth } from "../context/AuthContext";

export default function ServiceDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [service, setService] = useState<Service | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [requirements, setRequirements] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [s, r] = await Promise.all([
          get<Service>(`/services/${id}`),
          get<Review[]>(`/services/${id}/reviews`),
        ]);
        setService(s);
        setReviews(r);
      } catch {
        setService(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const orderNow = async (e: FormEvent) => {
    e.preventDefault();
    if (!user) {
      nav("/login", { state: { from: `/services/${id}` } });
      return;
    }
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const order = await post<Order>("/orders", {
        service_id: Number(id),
        requirements,
      });
      setSuccess(`Order #${order.id} placed! The provider has been notified.`);
      setRequirements("");
    } catch (err: any) {
      if (err.status === 402) {
        setError("Insufficient wallet balance — top up your wallet and try again.");
      } else {
        setError(err.message || "Could not place the order");
      }
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Spinner label="Loading service…" />;
  if (!service)
    return (
      <div className="mx-auto max-w-3xl px-4 pt-16">
        <EmptyState
          icon={<Sparkles size={28} />}
          title="Service not found"
          subtitle="This service may have been removed or paused by the provider."
          action={<Link to="/services" className="btn-primary">Browse services</Link>}
        />
      </div>
    );

  const tags = service.tags.split(",").map((t) => t.trim()).filter(Boolean);

  return (
    <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6">
      <Link to="/services" className="mb-6 inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={15} /> Back to marketplace
      </Link>

      <div className="grid gap-8 lg:grid-cols-[1fr,400px]">
        {/* ---- Main ---- */}
        <div>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <span className="rounded-lg bg-indigo-500/15 px-2.5 py-1 text-xs font-medium text-indigo-300">
              {service.category.name}
            </span>
            <Stars value={service.rating_avg} count={service.rating_count} size={16} />
            <span className="text-xs text-slate-500">{service.orders_count} orders</span>
          </div>
          <h1 className="font-display text-3xl font-bold leading-tight text-white sm:text-4xl">
            {service.title}
          </h1>

          {/* provider */}
          <div className="glass mt-6 flex flex-wrap items-center gap-4 rounded-2xl p-4">
            <Avatar user={service.provider} size={48} />
            <div className="flex-1">
              <div className="font-semibold text-white">{service.provider.full_name}</div>
              <div className="text-sm text-slate-400">{service.provider.headline || "AI specialist"}</div>
            </div>
            <div className="rounded-xl border border-emerald-400/25 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300">
              <ShieldCheck size={13} className="mr-1 inline" /> Vetted provider
            </div>
          </div>

          <div className="glass mt-6 rounded-2xl p-6">
            <h2 className="mb-3 font-display text-lg font-semibold text-white">About this service</h2>
            <p className="whitespace-pre-line leading-relaxed text-slate-300">{service.description}</p>
            {tags.length > 0 && (
              <div className="mt-5 flex flex-wrap gap-2">
                {tags.map((t) => (
                  <span key={t} className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-400">
                    <Tag size={11} /> {t}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* reviews */}
          <div className="mt-8">
            <h2 className="mb-4 font-display text-xl font-semibold text-white">
              Reviews {reviews.length > 0 && <span className="text-slate-500">({reviews.length})</span>}
            </h2>
            {reviews.length === 0 ? (
              <div className="glass rounded-2xl p-6 text-sm text-slate-400">
                No reviews yet — be the first client to order this service.
              </div>
            ) : (
              <div className="space-y-4">
                {reviews.map((r) => (
                  <div key={r.id} className="glass rounded-2xl p-5">
                    <div className="mb-2 flex items-center gap-3">
                      <Avatar user={r.author} size={34} />
                      <div>
                        <div className="text-sm font-semibold text-white">{r.author.full_name}</div>
                        <div className="text-xs text-slate-500">{fmtDate(r.created_at)}</div>
                      </div>
                      <div className="ml-auto flex gap-0.5 text-amber-400">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <Star key={i} size={13} fill={i < r.rating ? "currentColor" : "none"} strokeWidth={i < r.rating ? 0 : 1.5} />
                        ))}
                      </div>
                    </div>
                    <p className="text-sm leading-relaxed text-slate-300">{r.comment}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ---- Order box ---- */}
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <div className="glass rounded-2xl p-6">
            <div className="mb-1 text-sm text-slate-400">Starting at</div>
            <div className="font-display text-4xl font-bold text-white">{fmtMoney(service.price_cents)}</div>
            <div className="mt-4 space-y-2.5 text-sm text-slate-300">
              <div className="flex items-center gap-2">
                <Clock size={15} className="text-indigo-400" /> {service.delivery_days}-day delivery
              </div>
              <div className="flex items-center gap-2">
                <ShieldCheck size={15} className="text-indigo-400" /> Payment protected until you approve
              </div>
              <div className="flex items-center gap-2">
                <Wallet size={15} className="text-indigo-400" /> Pay with your QORA wallet
              </div>
            </div>

            {user?.role === "provider" ? (
              <div className="mt-6 rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
                Provider accounts can't order services. Switch to a consumer account to buy.
              </div>
            ) : user?.id === service.provider.id ? (
              <div className="mt-6 rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
                This is your service — manage it from the Provider dashboard.
              </div>
            ) : (
              <form onSubmit={orderNow} className="mt-6">
                <label className="mb-2 block text-sm font-medium text-slate-300">
                  Project requirements
                </label>
                <textarea
                  value={requirements}
                  onChange={(e) => setRequirements(e.target.value)}
                  rows={4}
                  placeholder="Describe your use case, data, deadline…"
                  className="input resize-none"
                />
                {error && (
                  <div className="mt-3 flex items-start gap-2 rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-300">
                    {error}
                    {error.includes("wallet") && (
                      <Link to="/wallet" className="ml-1 font-semibold underline">Top up now</Link>
                    )}
                  </div>
                )}
                {success && (
                  <div className="mt-3 flex items-center gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-3 py-2.5 text-sm text-emerald-300">
                    <CheckCircle2 size={16} /> {success}
                  </div>
                )}
                <button type="submit" disabled={busy} className="btn-primary mt-4 w-full !py-3">
                  {busy ? "Placing order…" : user ? "Order now" : "Sign in to order"}
                </button>
                <p className="mt-3 flex items-center justify-center gap-1.5 text-xs text-slate-500">
                  <MessageSquare size={12} /> Full refund if you cancel before completion
                </p>
              </form>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
