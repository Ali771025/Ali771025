import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Sparkles, ArrowRight, ShieldCheck, Wallet, MessageSquare, Cpu, BarChart3,
  Mic, Workflow, FileText, Image, Target, Bot, Star,
} from "lucide-react";
import { get, fmtMoney } from "../api/client";
import type { Category, Service, Stats } from "../types";
import { ServiceCard, SkeletonGrid, SectionHeader } from "../components/ui";

const ICONS: Record<string, any> = {
  "message-square": MessageSquare, image: Image, "bar-chart-3": BarChart3,
  mic: Mic, workflow: Workflow, "file-text": FileText, cpu: Cpu, target: Target,
};

const STEPS = [
  { icon: <Sparkles />, title: "Describe your need", text: "Browse the catalog or ask the AI Concierge to match you with the right service in seconds." },
  { icon: <Wallet />, title: "Order with your wallet", text: "Top up once, order instantly. Funds stay protected until you approve the delivery." },
  { icon: <ShieldCheck />, title: "Approve & pay", text: "Review the delivery, release payment, and rate the provider. Cancel anytime before completion." },
];

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [cats, setCats] = useState<Category[]>([]);
  const [featured, setFeatured] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [s, c, f] = await Promise.all([
          get<Stats>("/stats"),
          get<Category[]>("/categories"),
          get<Service[]>("/services?sort=rating&limit=6"),
        ]);
        setStats(s);
        setCats(c);
        setFeatured(f);
      } catch {
        /* backend offline — page still renders */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div>
      {/* ---------------- Hero ---------------- */}
      <section className="hero-glow grid-bg relative overflow-hidden">
        <div className="mx-auto max-w-7xl px-4 pb-20 pt-20 text-center sm:px-6 sm:pt-28">
          <div className="fade-up mx-auto mb-6 flex w-fit items-center gap-2 rounded-full border border-indigo-400/25 bg-indigo-500/10 px-4 py-1.5 text-sm text-indigo-300">
            <Bot size={15} /> AI Concierge is live — ask it anything
          </div>
          <h1 className="fade-up mx-auto max-w-4xl font-display text-4xl font-bold leading-tight text-white sm:text-6xl lg:text-7xl">
            The consumer network for{" "}
            <span className="gradient-text">AI services</span>
          </h1>
          <p className="fade-up mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-400">
            Discover vetted AI providers, order production-grade services — chatbots, vision,
            data, voice, automation — and pay only when the work is delivered.
          </p>
          <div className="fade-up mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link to="/services" className="btn-primary !px-7 !py-3.5 text-base">
              Explore services <ArrowRight size={18} />
            </Link>
            <Link to="/assistant" className="btn-ghost !px-7 !py-3.5 text-base">
              <Bot size={18} /> Ask the AI Concierge
            </Link>
          </div>

          {stats && (
            <div className="fade-up mx-auto mt-14 grid max-w-3xl grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                { v: stats.services, l: "AI services" },
                { v: stats.providers, l: "Expert providers" },
                { v: fmtMoney(stats.gmv_cents), l: "GMV processed" },
                { v: `★ ${stats.avg_rating || "—"}`, l: "Average rating" },
              ].map((x) => (
                <div key={x.l} className="glass rounded-2xl px-4 py-5">
                  <div className="font-display text-2xl font-bold text-white">{x.v}</div>
                  <div className="mt-1 text-xs uppercase tracking-wider text-slate-500">{x.l}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* ---------------- Categories ---------------- */}
      <section className="mx-auto max-w-7xl px-4 sm:px-6">
        <SectionHeader
          kicker="Capabilities"
          title="Every AI capability, one network"
          subtitle="QORA organizes the AI services market into clear capability areas so you always find the right expert."
        />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {cats.map((c) => {
            const Icon = ICONS[c.icon] ?? Sparkles;
            return (
              <Link
                key={c.id}
                to={`/services?category=${c.slug}`}
                className="glass card-hover group rounded-2xl p-5"
              >
                <div className="mb-3 inline-flex rounded-xl bg-indigo-500/15 p-2.5 text-indigo-300 transition group-hover:bg-indigo-500/25">
                  <Icon size={20} />
                </div>
                <h3 className="font-semibold text-white">{c.name}</h3>
                <p className="mt-1 line-clamp-2 text-xs text-slate-500">{c.description}</p>
              </Link>
            );
          })}
        </div>
      </section>

      {/* ---------------- Featured ---------------- */}
      <section className="mx-auto mt-24 max-w-7xl px-4 sm:px-6">
        <SectionHeader
          kicker="Top rated"
          title="Featured AI services"
          subtitle="Hand-picked services with the best reviews from real orders."
          action={
            <Link to="/services" className="btn-ghost !py-2 !text-sm">
              View all <ArrowRight size={15} />
            </Link>
          }
        />
        {loading ? <SkeletonGrid /> : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {featured.map((s) => <ServiceCard key={s.id} service={s} />)}
          </div>
        )}
      </section>

      {/* ---------------- How it works ---------------- */}
      <section className="mx-auto mt-28 max-w-7xl px-4 sm:px-6">
        <SectionHeader
          kicker="How it works"
          title="From idea to delivered AI in three steps"
        />
        <div className="grid gap-6 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <div key={s.title} className="glass relative rounded-2xl p-7">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500/25 to-violet-500/25 text-indigo-300">
                {s.icon}
              </div>
              <div className="absolute right-6 top-6 font-display text-5xl font-bold text-white/5">
                0{i + 1}
              </div>
              <h3 className="mb-2 font-display text-lg font-semibold text-white">{s.title}</h3>
              <p className="text-sm leading-relaxed text-slate-400">{s.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ---------------- Provider CTA ---------------- */}
      <section className="mx-auto mt-28 max-w-7xl px-4 sm:px-6">
        <div className="relative overflow-hidden rounded-3xl border border-indigo-400/20 bg-gradient-to-br from-indigo-950/60 via-[#0b0b1d] to-violet-950/50 px-8 py-14 sm:px-14">
          <div className="absolute -right-20 -top-20 h-72 w-72 rounded-full bg-violet-600/20 blur-3xl" />
          <div className="absolute -bottom-24 left-10 h-72 w-72 rounded-full bg-indigo-600/20 blur-3xl" />
          <div className="relative max-w-2xl">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-violet-400/25 bg-violet-500/10 px-3.5 py-1.5 text-xs font-semibold text-violet-300">
              <Star size={13} /> For AI builders
            </div>
            <h2 className="font-display text-3xl font-bold text-white sm:text-4xl">
              Turn your AI expertise into revenue
            </h2>
            <p className="mt-4 text-lg leading-relaxed text-slate-300">
              Publish your service, set your price, and reach clients who are ready to buy.
              QORA handles payments, escrow-style protection and reputation — you keep 90% of every sale.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/register" className="btn-primary !px-7 !py-3.5">
                Become a provider <ArrowRight size={18} />
              </Link>
              <Link to="/services" className="btn-ghost !px-7 !py-3.5">
                See what sells
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
