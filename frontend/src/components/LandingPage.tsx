import type { ReactNode } from "react";
import { Link } from "react-router";
import { ArrowRight, Blocks, Github, Globe, Network, Search, ShieldCheck } from "lucide-react";
import { useAuthStore } from "../stores/authStore";
import { Seo } from "./Seo";

const KEYWORDS =
  "OSINT platform, link analysis, graph intelligence, open source intelligence, visual investigation, entity relationships, cybersecurity analysis";

export function LandingPage() {
  const { user, authEnabled } = useAuthStore();
  const primaryHref = "/projects";
  const primaryLabel = authEnabled && user ? "Open Workspace" : "Start Investigating";

  return (
    <>
      <Seo
        title="OpenGraph Intel | Open-Source OSINT Link Analysis Platform"
        description="Investigate entities, map relationships, and run graph-native OSINT workflows with an open-source visual intelligence platform."
        path="/"
        keywords={KEYWORDS}
      />
      <div className="min-h-screen bg-bg text-text">
        <header className="sticky top-0 z-20 border-b border-white/10 bg-bg/80 backdrop-blur">
          <div className="mx-auto max-w-6xl px-4 py-4 sm:px-6">
            <div className="flex items-center justify-between gap-4">
              <Link
                to="/"
                className="min-w-0 text-xs font-semibold tracking-[0.18em] uppercase text-text sm:text-sm"
              >
                OpenGraph Intel
              </Link>
              <Link
                to={primaryHref}
                className="shrink-0 rounded-full border border-accent/40 bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
              >
                <span className="sm:hidden">{authEnabled && user ? "Open" : "Start"}</span>
                <span className="hidden sm:inline">{primaryLabel}</span>
              </Link>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 sm:mt-4">
              <nav className="flex flex-wrap items-center gap-2 text-sm">
                <Link
                  to="/discover"
                  className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-text-muted hover:text-text"
                >
                  Discover
                </Link>
                <a
                  href="https://github.com/khashashin/ogi"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-text-muted hover:text-text"
                >
                  <Github size={14} />
                  GitHub
                </a>
                <a
                  href="https://github.com/opengraphintel/ogi-transforms"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-text-muted hover:text-text"
                >
                  <Blocks size={14} />
                  Transform Hub
                </a>
              </nav>
            </div>
          </div>
        </header>

        <main>
          <section className="relative overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.35),_transparent_35%),radial-gradient(circle_at_80%_20%,_rgba(34,197,94,0.18),_transparent_28%),linear-gradient(180deg,_rgba(255,255,255,0.03),_rgba(15,17,23,0))]" />
            <div className="absolute inset-x-0 top-20 mx-auto h-px max-w-5xl bg-gradient-to-r from-transparent via-white/15 to-transparent" />
            <div className="relative mx-auto grid max-w-6xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[1.2fr_0.8fr] lg:items-center lg:py-28">
              <div>
                <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-accent/30 bg-surface/70 px-3 py-1 text-xs uppercase tracking-[0.18em] text-accent">
                  Open Source Visual Intelligence
                </div>
                <h1 className="max-w-3xl text-4xl font-semibold leading-tight sm:text-5xl">
                  Investigate relationships, not just records.
                </h1>
                <p className="mt-6 max-w-2xl text-base leading-7 text-text-muted sm:text-lg">
                  OpenGraph Intel helps analysts turn domains, people, documents, and infrastructure into a navigable graph. Build cases faster, run transforms in context, and keep the chain of evidence visible.
                </p>
                <div className="mt-8 flex flex-wrap gap-3">
                  <Link
                    to={primaryHref}
                    className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-3 text-sm font-medium text-white hover:bg-accent-hover"
                  >
                    {primaryLabel}
                    <ArrowRight size={16} />
                  </Link>
                  <Link
                    to="/discover"
                    className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-5 py-3 text-sm font-medium text-text hover:border-accent/50"
                  >
                    Browse Public Projects
                  </Link>
                  <a
                    href="https://github.com/khashashin/ogi"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 rounded-full border border-border bg-transparent px-5 py-3 text-sm font-medium text-text-muted hover:border-accent/50 hover:text-text"
                  >
                    <Github size={16} />
                    GitHub
                  </a>
                  <a
                    href="https://github.com/opengraphintel/ogi-transforms"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 rounded-full border border-border bg-transparent px-5 py-3 text-sm font-medium text-text-muted hover:border-accent/50 hover:text-text"
                  >
                    <Blocks size={16} />
                    Transform Hub
                  </a>
                </div>
                <div className="mt-10 grid gap-4 text-sm text-text-muted sm:grid-cols-3">
                  <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                    <div className="text-2xl font-semibold text-text">Graph-first</div>
                    <p className="mt-1">Entities, edges, transforms, and analyst review in one workspace.</p>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                    <div className="text-2xl font-semibold text-text">OSINT-ready</div>
                    <p className="mt-1">Built around practical enrichment workflows, not generic dashboards.</p>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
                    <div className="text-2xl font-semibold text-text">Open-source</div>
                    <p className="mt-1">Transparent, extensible, and designed for community transforms.</p>
                  </div>
                </div>
              </div>

              <div className="rounded-[28px] border border-white/10 bg-surface/80 p-5 shadow-2xl shadow-black/25 backdrop-blur">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-text-muted">Analyst Canvas</p>
                    <p className="mt-1 text-sm font-medium text-text">Live graph investigation workflow</p>
                  </div>
                  <div className="rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs text-accent">
                    Active
                  </div>
                </div>
                <div className="rounded-3xl border border-white/8 bg-[#10131d] p-4">
                  <div className="grid gap-3">
                    <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] p-3">
                      <div>
                        <p className="text-sm font-medium text-text">Entity graph</p>
                        <p className="text-xs text-text-muted">Pivot from people to domains to infrastructure</p>
                      </div>
                      <Network className="text-accent" size={18} />
                    </div>
                    <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] p-3">
                      <div>
                        <p className="text-sm font-medium text-text">Transform pipeline</p>
                        <p className="text-xs text-text-muted">Run contextual enrichments without leaving the case</p>
                      </div>
                      <Search className="text-accent" size={18} />
                    </div>
                    <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] p-3">
                      <div>
                        <p className="text-sm font-medium text-text">Shared investigations</p>
                        <p className="text-xs text-text-muted">Collaborate on projects with controlled visibility</p>
                      </div>
                      <ShieldCheck className="text-accent" size={18} />
                    </div>
                  </div>
                  <div className="mt-4 rounded-2xl border border-white/8 bg-gradient-to-br from-accent/18 via-white/[0.03] to-emerald-400/10 p-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-accent">Use Cases</p>
                    <ul className="mt-3 space-y-2 text-sm text-text-muted">
                      <li>Threat hunting and infrastructure pivoting</li>
                      <li>Corporate attribution and exposure mapping</li>
                      <li>Public-source investigative research</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
            <div className="grid gap-6 md:grid-cols-3">
              <FeatureCard
                icon={<Globe size={18} />}
                title="Map the public surface"
                description="Start from a domain, person, URL, or document and expand outward with graph-native context."
              />
              <FeatureCard
                icon={<Network size={18} />}
                title="Keep relationships visible"
                description="See how entities connect across DNS, social, documents, locations, and analyst findings."
              />
              <FeatureCard
                icon={<ShieldCheck size={18} />}
                title="Review before you trust"
                description="Use confidence, provenance, and evidence snippets to keep automation accountable."
              />
            </div>
          </section>
        </main>

        <footer className="border-t border-white/8">
          <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm text-text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <p className="max-w-xl">
              OpenGraph Intel is an open-source platform for graph-based OSINT and link analysis.
            </p>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              <Link to="/terms" className="hover:text-text">Terms</Link>
              <Link to="/privacy" className="hover:text-text">Privacy</Link>
              <Link to="/discover" className="hover:text-text">Discover</Link>
              <a href="https://github.com/khashashin/ogi" target="_blank" rel="noreferrer" className="hover:text-text">GitHub</a>
              <a href="https://github.com/opengraphintel/ogi-transforms" target="_blank" rel="noreferrer" className="hover:text-text">Transform Hub</a>
            </div>
          </div>
        </footer>
      </div>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            name: "OpenGraph Intel",
            applicationCategory: "SecurityApplication",
            operatingSystem: "Web",
            description:
              "Open-source visual intelligence platform for OSINT, link analysis, and graph-based investigation workflows.",
            url: typeof window !== "undefined" ? window.location.origin : "",
          }),
        }}
      />
    </>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-3xl border border-white/8 bg-surface/80 p-6">
      <div className="mb-4 inline-flex rounded-2xl border border-accent/30 bg-accent/10 p-3 text-accent">
        {icon}
      </div>
      <h2 className="text-lg font-medium text-text">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-text-muted">{description}</p>
    </div>
  );
}
