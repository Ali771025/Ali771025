import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Store, PlusCircle, Pencil, Trash2, PauseCircle, PlayCircle, Package, Wallet,
  TrendingUp, X, Star, BarChart3,
} from "lucide-react";
import { get, post, patch, del, fmtMoney, fmtDate } from "../api/client";
import type { Category, Order, Service, Wallet as WalletT } from "../types";
import { useAuth } from "../context/AuthContext";
import { OrderCard, Spinner, EmptyState, SectionHeader, StatCard, StatusBadge } from "../components/ui";

const EMPTY_FORM = {
  title: "", description: "", price: "", delivery_days: "7",
  category_id: "", tags: "", status: "active",
};

export default function Provider() {
  const { user } = useAuth();
  const [services, setServices] = useState<Service[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [wallet, setWallet] = useState<WalletT | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Service | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  const load = async () => {
    setLoading(true);
    try {
      const [all, o, c, w] = await Promise.all([
        get<Service[]>("/services?limit=60&sort=newest"),
        get<Order[]>("/orders?role=provider"),
        get<Category[]>("/categories"),
        get<WalletT>("/wallet"),
      ]);
      setServices(all.filter((s) => s.provider.id === user?.id));
      setOrders(o);
      setCats(c);
      setWallet(w);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM, category_id: String(cats[0]?.id ?? "") });
    setShowForm(true);
    setError("");
  };

  const openEdit = (s: Service) => {
    setEditing(s);
    setForm({
      title: s.title,
      description: s.description,
      price: String(s.price_cents / 100),
      delivery_days: String(s.delivery_days),
      category_id: String(s.category.id),
      tags: s.tags,
      status: s.status,
    });
    setShowForm(true);
    setError("");
  };

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    const payload = {
      title: form.title,
      description: form.description,
      price_cents: Math.round(Number(form.price) * 100),
      delivery_days: Number(form.delivery_days),
      category_id: Number(form.category_id),
      tags: form.tags,
      status: form.status,
    };
    try {
      if (editing) await patch(`/services/${editing.id}`, payload);
      else await post("/services", payload);
      setShowForm(false);
      await load();
    } catch (err: any) {
      setError(err.message || "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const togglePause = async (s: Service) => {
    setBusy(true);
    try {
      await patch(`/services/${s.id}`, { status: s.status === "active" ? "paused" : "active" });
      await load();
    } finally {
      setBusy(false);
    }
  };

  const remove = async (s: Service) => {
    if (!confirm(`Delete “${s.title}”?`)) return;
    setBusy(true);
    try {
      await del(`/services/${s.id}`);
      await load();
    } catch (err: any) {
      setError(err.message || "Delete failed");
    } finally {
      setBusy(false);
    }
  };

  const onAction = async (action: string, order: Order) => {
    setBusy(true);
    setError("");
    try {
      const status =
        action === "accept" ? "in_progress" : action === "deliver" ? "delivered" : "cancelled";
      await patch(`/orders/${order.id}/status`, { status });
      await load();
    } catch (err: any) {
      setError(err.message || "Action failed");
    } finally {
      setBusy(false);
    }
  };

  const earnings = wallet
    ? wallet.transactions.filter((t) => t.kind === "earning").reduce((a, t) => a + t.amount_cents, 0)
    : 0;
  const activeServices = services.filter((s) => s.status === "active").length;
  const openOrders = orders.filter((o) => ["pending", "in_progress", "delivered"].includes(o.status)).length;

  return (
    <div className="mx-auto max-w-7xl px-4 pt-12 sm:px-6">
      <SectionHeader
        kicker="Provider workspace"
        title="Sell your AI services"
        subtitle="Manage your catalog, fulfill orders and track earnings. You keep 90% of every sale."
        action={
          <button onClick={openCreate} className="btn-primary !py-2.5 !text-sm">
            <PlusCircle size={16} /> New service
          </button>
        }
      />

      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={<Store size={16} />} label="Active services" value={activeServices} />
        <StatCard icon={<Package size={16} />} label="Open orders" value={openOrders} />
        <StatCard icon={<TrendingUp size={16} />} label="Total earned" value={fmtMoney(earnings)} />
        <StatCard icon={<Wallet size={16} />} label="Wallet balance" value={wallet ? fmtMoney(wallet.balance_cents) : "—"} />
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">{error}</div>
      )}

      {loading ? (
        <Spinner />
      ) : (
        <>
          {/* services */}
          <h2 className="mb-4 font-display text-xl font-semibold text-white">Your services</h2>
          {services.length === 0 ? (
            <div className="mb-10">
              <EmptyState
                icon={<Store size={28} />}
                title="No services published yet"
                subtitle="Create your first AI service — set a price and delivery time, and it goes live on the marketplace."
                action={<button onClick={openCreate} className="btn-primary"><PlusCircle size={16} /> Create service</button>}
              />
            </div>
          ) : (
            <div className="mb-10 space-y-3">
              {services.map((s) => (
                <div key={s.id} className="glass flex flex-wrap items-center gap-4 rounded-2xl p-4">
                  <div className="min-w-[220px] flex-1">
                    <div className="flex items-center gap-2.5">
                      <Link to={`/services/${s.id}`} className="font-semibold text-white hover:text-indigo-300">
                        {s.title}
                      </Link>
                      <StatusBadge status={s.status} />
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                      <span>{s.category.name}</span>
                      <span className="inline-flex items-center gap-1"><Star size={11} className="text-amber-400" /> {s.rating_avg || "new"} ({s.rating_count})</span>
                      <span>{s.orders_count} orders</span>
                      <span>{s.delivery_days}d delivery</span>
                    </div>
                  </div>
                  <div className="font-display text-lg font-bold text-white">{fmtMoney(s.price_cents)}</div>
                  <div className="flex items-center gap-1.5">
                    <button onClick={() => openEdit(s)} className="rounded-xl border border-white/10 p-2 text-slate-300 transition hover:border-indigo-400/40 hover:text-indigo-300" title="Edit">
                      <Pencil size={15} />
                    </button>
                    <button onClick={() => togglePause(s)} className="rounded-xl border border-white/10 p-2 text-slate-300 transition hover:border-amber-400/40 hover:text-amber-300" title={s.status === "active" ? "Pause" : "Activate"}>
                      {s.status === "active" ? <PauseCircle size={15} /> : <PlayCircle size={15} />}
                    </button>
                    <button onClick={() => remove(s)} className="rounded-xl border border-white/10 p-2 text-slate-300 transition hover:border-rose-400/40 hover:text-rose-300" title="Delete">
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* incoming orders */}
          <h2 className="mb-4 font-display text-xl font-semibold text-white">Incoming orders</h2>
          {orders.length === 0 ? (
            <EmptyState
              icon={<Package size={28} />}
              title="No orders yet"
              subtitle="When clients order your services they'll appear here with fulfillment actions."
              action={<Link to="/services" className="btn-ghost !py-2 !text-sm"><BarChart3 size={15} /> See the marketplace</Link>}
            />
          ) : (
            <div className="space-y-4">
              {orders.map((o) => (
                <OrderCard key={o.id} order={o} perspective="provider" onAction={onAction} busy={busy} />
              ))}
            </div>
          )}
        </>
      )}

      {/* service form modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/70 p-4 backdrop-blur-sm">
          <div className="glass w-full max-w-lg rounded-3xl p-7">
            <div className="mb-5 flex items-start justify-between">
              <h3 className="font-display text-xl font-bold text-white">
                {editing ? "Edit service" : "New service"}
              </h3>
              <button onClick={() => setShowForm(false)} className="rounded-xl p-1.5 text-slate-400 hover:bg-white/5 hover:text-white">
                <X size={18} />
              </button>
            </div>
            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-300">Title</label>
                <input required minLength={4} value={form.title} onChange={(e) => set("title", e.target.value)} className="input" placeholder="Custom GPT Support Chatbot" />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-300">Description</label>
                <textarea required minLength={10} rows={4} value={form.description} onChange={(e) => set("description", e.target.value)} className="input resize-none" placeholder="What exactly do clients get? Scope, deliverables, tech…" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-300">Price (USD)</label>
                  <input required type="number" min="1" step="1" value={form.price} onChange={(e) => set("price", e.target.value)} className="input" placeholder="490" />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-300">Delivery (days)</label>
                  <input required type="number" min="1" max="90" value={form.delivery_days} onChange={(e) => set("delivery_days", e.target.value)} className="input" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-300">Category</label>
                  <select required value={form.category_id} onChange={(e) => set("category_id", e.target.value)} className="input cursor-pointer">
                    {cats.map((c) => (
                      <option key={c.id} value={c.id} className="bg-[#12121f]">{c.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-300">Status</label>
                  <select value={form.status} onChange={(e) => set("status", e.target.value)} className="input cursor-pointer">
                    <option value="active" className="bg-[#12121f]">Active</option>
                    <option value="draft" className="bg-[#12121f]">Draft</option>
                    <option value="paused" className="bg-[#12121f]">Paused</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-300">Tags (comma separated)</label>
                <input value={form.tags} onChange={(e) => set("tags", e.target.value)} className="input" placeholder="chatbot, rag, llm" />
              </div>
              {error && <div className="rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-300">{error}</div>}
              <div className="flex gap-2 pt-1">
                <button type="button" onClick={() => setShowForm(false)} className="btn-ghost flex-1">Cancel</button>
                <button type="submit" disabled={busy} className="btn-primary flex-1">
                  {busy ? "Saving…" : editing ? "Save changes" : "Publish service"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
