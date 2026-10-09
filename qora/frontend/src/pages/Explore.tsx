import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Compass, Star, ShieldCheck, UserCheck, Plus, Check } from "lucide-react";
import { del, get, post, DiscoveryItem, fmtScore } from "../api";
import { PageHeader, Spinner } from "../ui";

export default function Explore() {
  const [items, setItems] = useState<DiscoveryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [params] = useSearchParams();
  const highlight = Number(params.get("s") || 0);

  const load = () => {
    setLoading(true);
    get<DiscoveryItem[]>("/services").then(setItems).catch(() => setItems([])).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const toggleFollow = async (id: number, followed: boolean) => {
    if (followed) await del(`/services/${id}/follow`);
    else await post(`/services/${id}/follow`);
    load();
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <PageHeader
        kicker="Service network"
        title="Explore AI services"
        subtitle="Ranked by intent relevance, outcome quality, personal fit, trust and freshness — not popularity. Following a service adds it to your personal toolkit and boosts future matches."
      />
      {loading ? <Spinner /> : (
        <div className="space-y-4">
          {items.map((it) => (
            <div key={it.service.id}
              className={`glass card-hover rounded-2xl p-6 ${highlight === it.service.id ? "ring-2 ring-indigo-400/60" : ""}`}>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-[260px] flex-1">
                  <div className="mb-1.5 flex flex-wrap items-center gap-2.5">
                    <h2 className="font-display text-lg font-semibold text-white">{it.service.name}</h2>
                    <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-xs text-slate-400">{it.service.category}</span>
                    <span className={`rounded-full border px-2.5 py-0.5 text-xs ${it.service.risk_level === "LOW" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-amber-500/30 bg-amber-500/10 text-amber-300"}`}>
                      risk: {it.service.risk_level}
                    </span>
                  </div>
                  <p className="text-sm text-slate-400">{it.service.summary}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                    <span className="inline-flex items-center gap-1.5"><UserCheck size={13} className="text-indigo-300" /> {it.creator.display_name}
                      {it.creator.verification_status === "verified" && <ShieldCheck size={12} className="text-emerald-300" />}</span>
                    <span className="inline-flex items-center gap-1"><Star size={12} className="text-amber-400" /> success {fmtScore(it.outcome.success_rate)} · {it.outcome.sessions} sessions</span>
                    <span>trust {fmtScore(it.trust.overall)} · {it.trust.freshness}</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-display text-2xl font-bold text-white">{fmtScore(it.rank.score)}</div>
                  <div className="text-xs text-slate-500">match score</div>
                  <button onClick={() => toggleFollow(it.service.id, it.followed)}
                    className={`mt-3 inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs font-semibold transition ${it.followed ? "border-emerald-400/40 bg-emerald-500/15 text-emerald-300" : "border-indigo-400/40 bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20"}`}>
                    {it.followed ? <><Check size={13} /> In your toolkit</> : <><Plus size={13} /> Follow</>}
                  </button>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-1.5 border-t border-white/5 pt-4">
                {Object.entries(it.rank.signals).map(([k, v]) => (
                  <span key={k} className="rounded-lg border border-white/5 bg-white/5 px-2 py-1 text-[10px] text-slate-500">
                    {k.replace(/_/g, " ")} <b className="text-slate-300">{Math.round((v as number) * 100)}</b>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
