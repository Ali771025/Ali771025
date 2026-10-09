import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, SlidersHorizontal, PackageSearch } from "lucide-react";
import { get } from "../api/client";
import type { Category, Service } from "../types";
import { ServiceCard, SkeletonGrid, EmptyState, SectionHeader } from "../components/ui";

const SORTS = [
  { id: "newest", label: "Newest" },
  { id: "rating", label: "Top rated" },
  { id: "price_asc", label: "Price ↑" },
  { id: "price_desc", label: "Price ↓" },
];

export default function Services() {
  const [params, setParams] = useSearchParams();
  const [services, setServices] = useState<Service[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(params.get("search") ?? "");

  const category = params.get("category") ?? "";
  const sort = params.get("sort") ?? "newest";

  useEffect(() => {
    get<Category[]>("/categories").then(setCats).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const qs = new URLSearchParams();
    if (search.trim()) qs.set("search", search.trim());
    if (category) qs.set("category", category);
    qs.set("sort", sort);
    get<Service[]>(`/services?${qs}`)
      .then(setServices)
      .catch(() => setServices([]))
      .finally(() => setLoading(false));
  }, [category, sort, search]);

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const activeCat = useMemo(() => cats.find((c) => c.slug === category), [cats, category]);

  return (
    <div className="mx-auto max-w-7xl px-4 pt-12 sm:px-6">
      <SectionHeader
        kicker="Marketplace"
        title="Explore AI services"
        subtitle="Production-ready services from vetted AI specialists — fixed prices, clear delivery times, real reviews."
      />

      {/* Toolbar */}
      <div className="glass mb-4 flex flex-wrap items-center gap-3 rounded-2xl p-4">
        <div className="relative min-w-[220px] flex-1">
          <Search size={17} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              const t = setTimeout(() => setParam("search", e.target.value), 350);
              return () => clearTimeout(t);
            }}
            placeholder="Search chatbot, vision, forecasting…"
            className="input !pl-10"
          />
        </div>
        <div className="flex items-center gap-2 text-slate-400">
          <SlidersHorizontal size={16} />
          <select
            value={sort}
            onChange={(e) => setParam("sort", e.target.value)}
            className="input !w-auto cursor-pointer !py-2 !pr-8 text-sm"
          >
            {SORTS.map((s) => (
              <option key={s.id} value={s.id} className="bg-[#12121f]">
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Category pills */}
      <div className="mb-8 flex flex-wrap gap-2">
        <button
          onClick={() => setParam("category", "")}
          className={`rounded-full border px-4 py-1.5 text-sm transition ${
            !category
              ? "border-indigo-400/50 bg-indigo-500/20 text-indigo-200"
              : "border-white/10 text-slate-400 hover:border-white/25 hover:text-slate-200"
          }`}
        >
          All
        </button>
        {cats.map((c) => (
          <button
            key={c.id}
            onClick={() => setParam("category", category === c.slug ? "" : c.slug)}
            className={`rounded-full border px-4 py-1.5 text-sm transition ${
              category === c.slug
                ? "border-indigo-400/50 bg-indigo-500/20 text-indigo-200"
                : "border-white/10 text-slate-400 hover:border-white/25 hover:text-slate-200"
            }`}
          >
            {c.name}
          </button>
        ))}
      </div>

      {loading ? (
        <SkeletonGrid n={6} />
      ) : services.length === 0 ? (
        <EmptyState
          icon={<PackageSearch size={28} />}
          title="No services found"
          subtitle={
            activeCat
              ? `Nothing in ${activeCat.name} matches your search yet. Try another category or keyword.`
              : "Try a different keyword or clear the filters."
          }
        />
      ) : (
        <>
          <p className="mb-4 text-sm text-slate-500">
            {services.length} service{services.length !== 1 && "s"}
            {activeCat ? ` in ${activeCat.name}` : ""}
            {search ? ` matching “${search}”` : ""}
          </p>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {services.map((s) => (
              <ServiceCard key={s.id} service={s} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
