import { useEffect, useState } from "react";
import { Link } from "react-router";
import { Loader2 } from "lucide-react";

import { api } from "../api/client";
import type { TelemetryInstanceSummary, TelemetryOverview } from "../api/client";
import { Seo } from "./Seo";

export function TelemetryAdminPage() {
  const [overview, setOverview] = useState<TelemetryOverview | null>(null);
  const [instances, setInstances] = useState<TelemetryInstanceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [overviewData, instanceData] = await Promise.all([
          api.telemetry.overview(),
          api.telemetry.instances(),
        ]);
        if (!cancelled) {
          setOverview(overviewData);
          setInstances(instanceData);
        }
      } catch (err) {
        if (!cancelled) {
          setError(String(err));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <Seo
        title="Telemetry Admin | OpenGraph Intel"
        description="Administrative telemetry overview for OGI cloud usage metrics."
        path="/admin/telemetry"
      />
      <div className="min-h-screen bg-bg">
        <header className="flex items-center h-12 px-4 bg-surface border-b border-border">
          <Link to="/projects" className="text-sm text-text-muted hover:text-text">
            Back
          </Link>
          <div className="ml-4 text-sm font-semibold text-text">Telemetry Admin</div>
        </header>
        <div className="max-w-6xl mx-auto px-4 py-8">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-text-muted">
              <Loader2 size={16} className="animate-spin text-accent" />
              Loading telemetry...
            </div>
          ) : error ? (
            <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm text-danger">
              {error}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
                <MetricCard label="Active Instances (30d)" value={String(overview?.active_instances_30d ?? 0)} />
                <MetricCard label="Self-Hosted (30d)" value={String(overview?.self_hosted_instances_30d ?? 0)} />
                <MetricCard label="Cloud (30d)" value={String(overview?.cloud_instances_30d ?? 0)} />
                <MetricCard
                  label="Latest Metric Date"
                  value={overview?.latest_metric_date ? new Date(overview.latest_metric_date).toLocaleDateString() : "n/a"}
                />
              </div>

              <div className="mb-6 rounded-lg border border-border bg-surface p-4">
                <h2 className="text-sm font-medium text-text mb-3">Version Distribution</h2>
                <div className="flex flex-col gap-2">
                  {(overview?.recent_versions ?? []).map((item) => (
                    <div key={item.version} className="flex items-center justify-between text-sm">
                      <span className="text-text">{item.version || "unknown"}</span>
                      <span className="text-text-muted">{item.count}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-border bg-surface overflow-hidden">
                <div className="px-4 py-3 border-b border-border text-sm font-medium text-text">
                  Recent Instances
                </div>
                <div className="divide-y divide-border">
                  {instances.map((instance) => (
                    <div key={instance.instance_id} className="px-4 py-3 text-sm">
                      <div className="flex flex-wrap items-center gap-3 mb-2">
                        <span className="font-mono text-xs text-text-muted">{instance.instance_id}</span>
                        <span className="px-1.5 py-0.5 rounded bg-bg text-xs text-text-muted">
                          {instance.deployment_mode}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-bg text-xs text-text-muted">
                          {instance.latest_telemetry_level}
                        </span>
                        <span className="text-text">{instance.latest_ogi_version}</span>
                        {instance.latest_country_code && (
                          <span className="text-text-muted">{instance.latest_country_code}</span>
                        )}
                      </div>
                      <div className="text-xs text-text-muted mb-2">
                        Last seen {new Date(instance.last_seen_at).toLocaleString()}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {instance.installed_transforms.map((transform) => (
                          <span
                            key={`${instance.instance_id}-${transform.name}`}
                            className="px-2 py-1 rounded bg-bg text-xs text-text-muted"
                          >
                            {transform.name}@{transform.version}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="text-xs uppercase tracking-wider text-text-muted mb-2">{label}</div>
      <div className="text-2xl font-semibold text-text">{value}</div>
    </div>
  );
}
