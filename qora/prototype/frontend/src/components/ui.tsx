import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Star, Sparkles, ShieldCheck, Clock, Users, ArrowRight, Wallet as WalletIcon } from "lucide-react";
import { initials } from "../api/client";
import type { Service, Order, UserPublic } from "../types";
import { fmtMoney } from "../api/client";

/* ---------- Avatar ---------- */
export function Avatar({ user, size = 36 }: { user: UserPublic | { full_name: string; avatar_color: string }; size?: number }) {
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
      style={{
        width: size,
        height: size,
        background: (user as any).avatar_color || "#6366f1",
        fontSize: size * 0.38,
      }}
    >
      {initials(user.full_name)}
    </span>
  );
}

/* ---------- Star rating ---------- */
export function Stars({ value, count, size = 14 }: { value: number; count?: number; size?: number }) {
  return (
    <span className="inline-flex items-center gap-1 text-amber-400">
      <Star size={size} fill="currentColor" strokeWidth={0} />
      <span className="font-semibold text-slate-200">{value > 0 ? value.toFixed(1) : "New"}</span>
      {count !== undefined && <span className="text-xs text-slate-500">({count})</span>}
    </span>
  );
}

/* ---------- Status badge ---------- */
const STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  in_progress: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  delivered: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  completed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  cancelled: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  active: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  paused: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  draft: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${
        STATUS_STYLES[status] ?? "bg-white/10 text-slate-300 border-white/10"
      }`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

/* ---------- Service card ---------- */
export function ServiceCard({ service }: { service: Service }) {
  return (
    <Link
      to={`/services/${service.id}`}
      className="glass card-hover group flex flex-col rounded-2xl p-5"
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <span className="rounded-lg bg-indigo-500/15 px-2.5 py-1 text-xs font-medium text-indigo-300">
          {service.category.name}
        </span>
        <Stars value={service.rating_avg} count={service.rating_count} />
      </div>
      <h3 className="mb-2 font-display text-lg font-semibold text-white group-hover:text-indigo-300 transition">
        {service.title}
      </h3>
      <p className="mb-4 line-clamp-2 text-sm leading-relaxed text-slate-400">{service.description}</p>
      <div className="mt-auto flex items-center justify-between border-t border-white/5 pt-4">
        <div className="flex items-center gap-2">
          <Avatar user={service.provider} size={28} />
          <span className="text-xs text-slate-400">{service.provider.full_name}</span>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-500">
            <Clock size={11} className="mr-1 inline" />
            {service.delivery_days}d
          </div>
          <div className="font-display text-lg font-bold text-white">{fmtMoney(service.price_cents)}</div>
        </div>
      </div>
    </Link>
  );
}

/* ---------- Spinner / skeleton / empty ---------- */
export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-slate-400">
      <Sparkles className="animate-spin text-indigo-400" size={20} />
      {label}
    </div>
  );
}

export function SkeletonGrid({ n = 6 }: { n?: number }) {
  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="glass rounded-2xl p-5">
          <div className="skeleton mb-3 h-5 w-24" />
          <div className="skeleton mb-2 h-5 w-3/4" />
          <div className="skeleton mb-1 h-3 w-full" />
          <div className="skeleton mb-4 h-3 w-2/3" />
          <div className="skeleton h-9 w-full" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ icon, title, subtitle, action }: { icon: ReactNode; title: string; subtitle: string; action?: ReactNode }) {
  return (
    <div className="glass flex flex-col items-center rounded-2xl px-6 py-14 text-center">
      <div className="mb-4 rounded-2xl bg-indigo-500/15 p-4 text-indigo-300">{icon}</div>
      <h3 className="mb-1 font-display text-lg font-semibold text-white">{title}</h3>
      <p className="mb-5 max-w-md text-sm text-slate-400">{subtitle}</p>
      {action}
    </div>
  );
}

/* ---------- Order card with role-aware actions ---------- */
export function OrderCard({
  order,
  perspective,
  onAction,
  busy,
}: {
  order: Order;
  perspective: "buyer" | "provider";
  onAction: (action: string, order: Order) => void;
  busy?: boolean;
}) {
  const isBuyer = perspective === "buyer";
  return (
    <div className="glass rounded-2xl p-5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to={`/services/${order.service_id}`} className="font-semibold text-white hover:text-indigo-300">
            {order.service.title}
          </Link>
          <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
            <span>#{order.id}</span>
            <span>·</span>
            <span>{isBuyer ? `by ${order.provider.full_name}` : `for ${order.buyer.full_name}`}</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={order.status} />
          <span className="font-display font-bold text-white">{fmtMoney(order.price_cents)}</span>
        </div>
      </div>
      {order.requirements && (
        <p className="mb-3 rounded-xl bg-white/5 px-3 py-2 text-sm text-slate-400">{order.requirements}</p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {isBuyer && order.status === "pending" && (
          <button disabled={busy} onClick={() => onAction("cancel", order)} className="btn-ghost !px-3.5 !py-1.5 !text-sm text-rose-300">
            Cancel order
          </button>
        )}
        {isBuyer && order.status === "delivered" && (
          <button disabled={busy} onClick={() => onAction("complete", order)} className="btn-primary !px-3.5 !py-1.5 !text-sm">
            Approve & pay
          </button>
        )}
        {isBuyer && order.status === "completed" && !order.review && (
          <button disabled={busy} onClick={() => onAction("review", order)} className="btn-primary !px-3.5 !py-1.5 !text-sm">
            <Star size={14} /> Leave a review
          </button>
        )}
        {isBuyer && order.review && (
          <span className="inline-flex items-center gap-1.5 text-xs text-emerald-300">
            <ShieldCheck size={14} /> Reviewed · {order.review.rating}★
          </span>
        )}
        {!isBuyer && order.status === "pending" && (
          <>
            <button disabled={busy} onClick={() => onAction("accept", order)} className="btn-primary !px-3.5 !py-1.5 !text-sm">
              Accept order
            </button>
            <button disabled={busy} onClick={() => onAction("cancel", order)} className="btn-ghost !px-3.5 !py-1.5 !text-sm text-rose-300">
              Decline
            </button>
          </>
        )}
        {!isBuyer && order.status === "in_progress" && (
          <button disabled={busy} onClick={() => onAction("deliver", order)} className="btn-primary !px-3.5 !py-1.5 !text-sm">
            Mark as delivered
          </button>
        )}
        {!isBuyer && order.status === "delivered" && (
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
            <Clock size={14} /> Waiting for client approval
          </span>
        )}
        {!isBuyer && order.status === "completed" && (
          <span className="inline-flex items-center gap-1.5 text-xs text-emerald-300">
            <WalletIcon size={14} /> Paid out to your wallet
          </span>
        )}
      </div>
    </div>
  );
}

/* ---------- Section header ---------- */
export function SectionHeader({ kicker, title, subtitle, action }: { kicker: string; title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-indigo-400">
          <Sparkles size={14} /> {kicker}
        </div>
        <h2 className="font-display text-2xl font-bold text-white sm:text-3xl">{title}</h2>
        {subtitle && <p className="mt-2 max-w-2xl text-slate-400">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function StatCard({ icon, label, value }: { icon: ReactNode; label: string; value: string | number }) {
  return (
    <div className="glass rounded-2xl p-5">
      <div className="mb-2 flex items-center gap-2 text-slate-400">
        <span className="rounded-lg bg-indigo-500/15 p-1.5 text-indigo-300">{icon}</span>
        <span className="text-sm">{label}</span>
      </div>
      <div className="font-display text-2xl font-bold text-white">{value}</div>
    </div>
  );
}

export function LearnMore({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="inline-flex items-center gap-1.5 font-semibold text-indigo-400 hover:text-indigo-300">
      {children} <ArrowRight size={16} />
    </Link>
  );
}

export { Users as UsersIcon };
