import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Package, Star, Wallet, X, Sparkles, Store } from "lucide-react";
import { get, patch, post, fmtMoney } from "../api/client";
import type { Order, Stats } from "../types";
import { useAuth } from "../context/AuthContext";
import { OrderCard, Spinner, EmptyState, SectionHeader, StatCard } from "../components/ui";

export default function Dashboard() {
  const { user } = useAuth();
  const [orders, setOrders] = useState<Order[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [reviewFor, setReviewFor] = useState<Order | null>(null);
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [o, w, s] = await Promise.all([
        get<Order[]>("/orders?role=buyer"),
        get<any>("/wallet"),
        get<Stats>("/stats"),
      ]);
      setOrders(o);
      setBalance(w.balance_cents);
      setStats(s);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onAction = async (action: string, order: Order) => {
    if (action === "review") {
      setReviewFor(order);
      setRating(5);
      setComment("");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await patch(`/orders/${order.id}/status`, {
        status: action === "cancel" ? "cancelled" : "completed",
      });
      await load();
    } catch (err: any) {
      setError(err.message || "Action failed");
    } finally {
      setBusy(false);
    }
  };

  const submitReview = async () => {
    if (!reviewFor) return;
    setBusy(true);
    try {
      await post("/reviews", { order_id: reviewFor.id, rating, comment });
      setReviewFor(null);
      await load();
    } catch (err: any) {
      setError(err.message || "Review failed");
    } finally {
      setBusy(false);
    }
  };

  const active = orders.filter((o) => ["pending", "in_progress", "delivered"].includes(o.status));

  return (
    <div className="mx-auto max-w-7xl px-4 pt-12 sm:px-6">
      <SectionHeader
        kicker={`Welcome back, ${user?.full_name.split(" ")[0]}`}
        title="Consumer dashboard"
        subtitle="Track your orders, approve deliveries and manage your wallet."
        action={
          user?.role === "consumer" ? (
            <Link to="/register" className="btn-ghost !py-2 !text-sm">
              <Store size={15} /> Switch to selling
            </Link>
          ) : undefined
        }
      />

      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={<Package size={16} />} label="Total orders" value={orders.length} />
        <StatCard icon={<Sparkles size={16} />} label="Active orders" value={active.length} />
        <StatCard icon={<Star size={16} />} label="Network services" value={stats?.services ?? "—"} />
        <StatCard icon={<Wallet size={16} />} label="Wallet balance" value={balance !== null ? fmtMoney(balance) : "—"} />
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">{error}</div>
      )}

      <h2 className="mb-4 font-display text-xl font-semibold text-white">Your orders</h2>
      {loading ? (
        <Spinner />
      ) : orders.length === 0 ? (
        <EmptyState
          icon={<Package size={28} />}
          title="No orders yet"
          subtitle="Explore the marketplace and order your first AI service — delivery times start at 5 days."
          action={<Link to="/services" className="btn-primary">Explore services</Link>}
        />
      ) : (
        <div className="space-y-4">
          {orders.map((o) => (
            <OrderCard key={o.id} order={o} perspective="buyer" onAction={onAction} busy={busy} />
          ))}
        </div>
      )}

      {/* review modal */}
      {reviewFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="glass w-full max-w-md rounded-3xl p-7">
            <div className="mb-5 flex items-start justify-between">
              <div>
                <h3 className="font-display text-xl font-bold text-white">Rate your experience</h3>
                <p className="mt-1 text-sm text-slate-400">{reviewFor.service.title}</p>
              </div>
              <button onClick={() => setReviewFor(null)} className="rounded-xl p-1.5 text-slate-400 hover:bg-white/5 hover:text-white">
                <X size={18} />
              </button>
            </div>
            <div className="mb-5 flex justify-center gap-2">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} onClick={() => setRating(n)} className="transition hover:scale-110">
                  <Star
                    size={34}
                    className={n <= rating ? "text-amber-400" : "text-slate-600"}
                    fill={n <= rating ? "currentColor" : "none"}
                    strokeWidth={1.5}
                  />
                </button>
              ))}
            </div>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={4}
              placeholder="What went well? What could be better?"
              className="input resize-none"
            />
            <button onClick={submitReview} disabled={busy} className="btn-primary mt-4 w-full !py-3">
              {busy ? "Submitting…" : "Submit review"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
