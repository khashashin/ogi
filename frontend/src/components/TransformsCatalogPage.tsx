import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Blocks, Filter, Search } from "lucide-react";
import { Link } from "react-router";
import { api } from "../api/client";
import type { TransformInfo } from "../types/transform";
import { Seo } from "./Seo";

const FEATURED_TRANSFORM_NAMES = [
  "username_search",
  "username_maigret",
  "domain_to_ip",
  "url_to_headers",
  "email_to_domain",
];

function matchesTransform(transform: TransformInfo, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;

  const haystack = [
    transform.display_name,
    transform.name,
    transform.description,
    transform.category,
    ...transform.input_types,
    ...transform.output_types,
    ...transform.api_key_services,
  ]
    .join(" ")
    .toLowerCase();

  return haystack.includes(normalized);
}

function formatTransformSubtitle(transform: TransformInfo): string {
  const inputs = transform.input_types.join(", ");
  const outputs = transform.output_types.join(", ");
  return `${transform.category} · ${inputs || "Any input"} -> ${outputs || "No outputs"}`;
}

export function TransformsCatalogPage() {
  const [transforms, setTransforms] = useState<TransformInfo[]>([]);
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<string>("All");
  const [expandedTransform, setExpandedTransform] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;
    api.transforms
      .list()
      .then((items) => {
        if (!isActive) return;
        const sorted = [...items].sort((a, b) => a.display_name.localeCompare(b.display_name));
        setTransforms(sorted);
        setExpandedTransform(sorted[0]?.name ?? null);
      })
      .catch((err) => {
        if (!isActive) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (isActive) setLoading(false);
      });

    return () => {
      isActive = false;
    };
  }, []);

  const categories = useMemo(() => {
    const unique = Array.from(new Set(transforms.map((transform) => transform.category))).sort();
    return ["All", ...unique];
  }, [transforms]);

  const filteredTransforms = useMemo(() => {
    return transforms.filter((transform) => {
      if (activeCategory !== "All" && transform.category !== activeCategory) {
        return false;
      }
      return matchesTransform(transform, query);
    });
  }, [activeCategory, query, transforms]);

  const featuredCount = transforms.filter((transform) =>
    FEATURED_TRANSFORM_NAMES.includes(transform.name)
  ).length;

  return (
    <>
      <Seo
        title="OpenGraph Intel | Transformer Collection"
        description="Browse OGI transformers, search by entity type and category, and inspect transform details before running them."
        path="/transforms"
        keywords="OGI transforms, OSINT transformers, entity enrichment transforms, link analysis automation"
      />
      <div className="min-h-screen bg-bg text-text">
        <header className="sticky top-0 z-20 border-b border-white/10 bg-bg/80 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
            <div>
              <Link to="/" className="text-xs font-semibold uppercase tracking-[0.18em] text-text">
                OpenGraph Intel
              </Link>
              <p className="mt-1 text-sm text-text-muted">Transformer Collection</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Link
                to="/"
                className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-text-muted hover:text-text"
              >
                Back to Landing
              </Link>
              <Link
                to="/projects"
                className="inline-flex items-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
              >
                Open Workspace
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
          <section className="grid gap-10 lg:grid-cols-[0.95fr_1.05fr] lg:items-start">
            <div className="rounded-[28px] border border-white/10 bg-surface/80 p-6 shadow-2xl shadow-black/20">
              <div className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-accent">
                <Blocks size={14} />
                Browse the toolset
              </div>
              <h1 className="mt-5 text-4xl font-semibold leading-tight text-text">
                Search every transformer before you pivot.
              </h1>
              <p className="mt-4 max-w-xl text-base leading-7 text-text-muted">
                Explore built-in and installed transformers by entity type, category, and output profile. This catalog is the public-facing view of the same transform metadata OGI uses in the workspace.
              </p>
              <div className="mt-8 grid gap-4 sm:grid-cols-3">
                <CatalogMetric label="Total transformers" value={String(transforms.length)} />
                <CatalogMetric label="Categories" value={String(categories.length - 1)} />
                <CatalogMetric label="Featured on landing" value={String(featuredCount)} />
              </div>
            </div>

            <div className="rounded-[28px] border border-white/10 bg-surface/70 p-5">
              <div className="flex flex-col gap-4">
                <label className="relative block">
                  <Search
                    size={16}
                    className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-text-muted"
                  />
                  <input
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search by name, description, category, or entity type"
                    className="w-full rounded-2xl border border-white/10 bg-bg/70 py-3 pl-11 pr-4 text-sm text-text outline-none transition focus:border-accent/50"
                  />
                </label>
                <div className="flex flex-wrap gap-2">
                  {categories.map((category) => (
                    <button
                      key={category}
                      type="button"
                      onClick={() => setActiveCategory(category)}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                        activeCategory === category
                          ? "bg-accent text-white"
                          : "border border-white/10 bg-white/[0.03] text-text-muted hover:text-text"
                      }`}
                    >
                      {category}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-text-muted">
                  <Filter size={13} />
                  {filteredTransforms.length} matches
                </div>
              </div>
            </div>
          </section>

          <section className="mt-10">
            {loading ? (
              <div className="rounded-[28px] border border-white/10 bg-surface/70 p-10 text-center text-sm text-text-muted">
                Loading transformer catalog...
              </div>
            ) : error ? (
              <div className="rounded-[28px] border border-red-400/20 bg-red-500/10 p-10 text-center text-sm text-red-100">
                Failed to load transformers: {error}
              </div>
            ) : filteredTransforms.length === 0 ? (
              <div className="rounded-[28px] border border-white/10 bg-surface/70 p-10 text-center text-sm text-text-muted">
                No transformers matched this search.
              </div>
            ) : (
              <div className="space-y-4">
                {filteredTransforms.map((transform) => {
                  const expanded = expandedTransform === transform.name;
                  return (
                    <article
                      key={transform.name}
                      className="overflow-hidden rounded-[24px] border border-white/10 bg-surface/75"
                    >
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedTransform((current) => (current === transform.name ? null : transform.name))
                        }
                        className="flex w-full flex-col gap-4 p-5 text-left transition hover:bg-white/[0.02] sm:flex-row sm:items-start sm:justify-between"
                      >
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full border border-accent/30 bg-accent/10 px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-accent">
                              {transform.category}
                            </span>
                            {transform.plugin_name && (
                              <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] uppercase tracking-[0.16em] text-text-muted">
                                Plugin: {transform.plugin_name}
                              </span>
                            )}
                          </div>
                          <h2 className="mt-3 text-xl font-medium text-text">{transform.display_name}</h2>
                          <p className="mt-2 text-sm leading-6 text-text-muted">{transform.description}</p>
                          <p className="mt-3 text-xs uppercase tracking-[0.14em] text-text-muted">
                            {formatTransformSubtitle(transform)}
                          </p>
                        </div>
                        <span className="text-xs font-medium uppercase tracking-[0.14em] text-text-muted">
                          {expanded ? "Hide details" : "View details"}
                        </span>
                      </button>
                      {expanded && (
                        <div className="grid gap-6 border-t border-white/10 px-5 py-5 text-sm text-text-muted lg:grid-cols-[0.9fr_1.1fr]">
                          <div>
                            <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-text">Entity Flow</h3>
                            <div className="mt-3 grid gap-3 sm:grid-cols-2">
                              <DetailCard
                                label="Input types"
                                values={transform.input_types.length > 0 ? transform.input_types : ["None declared"]}
                              />
                              <DetailCard
                                label="Output types"
                                values={transform.output_types.length > 0 ? transform.output_types : ["None declared"]}
                              />
                            </div>
                          </div>
                          <div>
                            <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-text">Configuration</h3>
                            {transform.settings.length === 0 ? (
                              <p className="mt-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                                This transformer runs without additional configurable settings.
                              </p>
                            ) : (
                              <div className="mt-3 space-y-3">
                                {transform.settings.map((setting) => (
                                  <div
                                    key={String(setting.name)}
                                    className="rounded-2xl border border-white/10 bg-white/[0.03] p-4"
                                  >
                                    <div className="flex flex-wrap items-center gap-2">
                                      <span className="font-medium text-text">{String(setting.display_name)}</span>
                                      <span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] uppercase tracking-[0.14em] text-text-muted">
                                        {String(setting.field_type)}
                                      </span>
                                      {Boolean(setting.required) && (
                                        <span className="rounded-full border border-accent/30 bg-accent/10 px-2 py-0.5 text-[11px] uppercase tracking-[0.14em] text-accent">
                                          Required
                                        </span>
                                      )}
                                    </div>
                                    <p className="mt-2 leading-6">{String(setting.description)}</p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </main>
      </div>
    </>
  );
}

function CatalogMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <div className="text-2xl font-semibold text-text">{value}</div>
      <p className="mt-1 text-sm text-text-muted">{label}</p>
    </div>
  );
}

function DetailCard({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-text">{label}</h4>
      <ul className="mt-3 space-y-2">
        {values.map((value) => (
          <li key={value} className="rounded-xl border border-white/8 bg-bg/40 px-3 py-2 text-sm text-text-muted">
            {value}
          </li>
        ))}
      </ul>
    </div>
  );
}
