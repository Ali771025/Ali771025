import { useEffect, useState } from "react";
import {
  ShieldCheck, Users, Package, TrendingUp, UserCheck, UserX, Wallet, Store, Star,
} from "lucide-react";
import { get, patch, fmtMoney, fmtDate, initials } from "../api/client";
import type { Order, Stats, User } from "../types";
import { Spinner, SectionHeader, StatCard, StatusBadge, Avatar, EmptyState } from "../components/ui";

export default function Admin() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"users" | "orders">("users");

  const load = async () => {
    setLoading(true);
    try {
      const [s, u, o] = await Promise.all([
        get<Stats>("/admin/stats"),
        get<User[]>("/admin/users"),
        get<Order[]>("/admin/orders"),
      ]);
      setStats(s);
      setUsers(u);
      setOrders(o);
    } catch (err: any) {
      setError(err.message || "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const toggleUser = async (u: User) => {
    setBusy(true);
    setError("");
    try {
      await patch(`/admin/users/${u.id}`, { is_active: !u.is_active });
      await load();
    } catch (err: any) {
      setError(err.message || "Update failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 pt-12 sm:px-6">
      <SectionHeader
        kicker="Platform operations"
        title="Admin console"
        subtitle="Network health, user management and order oversight."
      />

      {loading ? (
        <Spinner />
      ) : (
        <>
          <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard icon={<TrendingUp size={16} />} label="GMV processed" value={stats ? fmtMoney(stats.gmv_cents) : "—"} />
            <StatCard icon={<Package size={16} />} label="Orders (completed)" value={`${stats?.completed_orders ?? 0} / ${stats?.orders ?? 0}`} />
            <StatCard icon={<Store size={16} />} label="Services · Providers" value={`${stats?.services ?? 0} · ${stats?.providers ?? 0}`} />
            <StatCard icon={<Star size={16} />} label="Avg rating" value={stats?.avg_rating ? `★ ${stats.avg_rating}` : "—"} />
          </div>

          {error && (
            <div className="mb-4 rounded-xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">{error}</div>
          )}

          {/* tabs */}
          <div className="mb-6 flex gap-2">
            {[
              { id: "users", label: "Users", icon: <Users size={15} /> },
              { id: "orders", label: "All orders", icon: <Package size={15} /> },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id as any)}
                className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition ${
                  tab === t.id
                    ? "border-indigo-400/50 bg-indigo-500/20 text-indigo-200"
                    : "border-white/10 text-slate-400 hover:border-white/25 hover:text-slate-200"
                }`}
              >
                {t.icon} {t.label}
              </button>
            ))}
          </div>

          {tab === "users" ? (
            <div className="glass overflow-x-auto rounded-2xl">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-xs uppercase tracking-wider text-slate-500">
                    <th className="px-5 py-4">User</th>
                    <th className="px-5 py-4">Role</th>
                    <th className="px-5 py-4">Joined</th>
                    <th className="px-5 py-4">Status</th>
                    <th className="px-5 py-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-white/5 transition hover:bg-white/[0.03]">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <Avatar user={u} size={34} />
                          <div>
                            <div className="font-medium text-white">{u.full_name}</div>
                            <div className="text-xs text-slate-500">{u.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${
                          u.role === "admin"
                            ? "border-violet-500/30 bg-violet-500/15 text-violet-300"
                            : u.role === "provider"
                              ? "border-sky-500/30 bg-sky-500/15 text-sky-300"
                              : "border-white/10 bg-white/5 text-slate-300"
                        }`}>
                          {u.role === "admin" ? <ShieldCheck size={11} /> : u.role === "provider" ? <Store size={11} /> : <Users size={11} />}
                          {u.role}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-slate-400">{fmtDate(u.created_at)}</td>
                      <td className="px-5 py-3.5">
                        <StatusBadge status={u.is_active ? "active" : "cancelled"} />
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <button
                          disabled={busy}
                          onClick={() => toggleUser(u)}
                          className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 ${
                            u.is_active
                              ? "border-rose-500/25 text-rose-300 hover:bg-rose-500/10"
                              : "border-emerald-500/25 text-emerald-300 hover:bg-emerald-500/10"
                          }`}
                        >
                          {u.is_active ? <><UserX size={13} /> Suspend</> : <><UserCheck size={13} /> Activate</>}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : orders.length === 0 ? (
            <EmptyState icon={<Package size={28} />} title="No orders yet" subtitle="Orders from all users will appear here." />
          ) : (
            <div className="glass overflow-x-auto rounded-2xl">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-xs uppercase tracking-wider text-slate-500">
                    <th className="px-5 py-4">Order</th>
                    <th className="px-5 py-4">Service</th>
                    <th className="px-5 py-4">Buyer → Provider</th>
                    <th className="px-5 py-4">Status</th>
                    <th className="px-5 py-4 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => (
                    <tr key={o.id} className="border-b border-white/5 transition hover:bg-white/[0.03]">
                      <td className="px-5 py-3.5 text-slate-400">#{o.id}<div className="text-xs text-slate-600">{fmtDate(o.created_at)}</div></td>
                      <td className="max-w-[220px] truncate px-5 py-3.5 font-medium text-white">{o.service.title}</td>
                      <td className="px-5 py-3.5 text-slate-400">
                        {o.buyer.full_name} <span className="text-slate-600">→</span> {o.provider.full_name}
                      </td>
                      <td className="px-5 py-3.5"><StatusBadge status={o.status} /></td>
                      <td className="px-5 py-3.5 text-right font-semibold text-white">{fmtMoney(o.price_cents)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
