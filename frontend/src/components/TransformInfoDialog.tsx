import { useEffect, useState } from "react";
import { BookOpen, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import type { TransformDocumentation, TransformInfo } from "../types/transform";
import { api } from "../api/client";
import { isUnverifiedTier } from "../lib/pluginRisk";

interface TransformInfoDialogProps {
  open: boolean;
  transform: TransformInfo | null;
  onClose: () => void;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <h3 className="text-xs font-semibold text-text">{title}</h3>
      {children}
    </div>
  );
}

function TypeList({ label, types }: { label: string; types: string[] }) {
  if (types.length === 0) return null;
  return (
    <div className="flex flex-wrap items-baseline gap-1">
      <span className="text-[10px] text-text-muted">{label}</span>
      {types.map((t) => (
        <span key={t} className="px-1.5 py-0.5 text-[10px] rounded bg-surface-hover text-text">
          {t}
        </span>
      ))}
    </div>
  );
}

export function TransformInfoDialog({ open, transform, onClose }: TransformInfoDialogProps) {
  const [doc, setDoc] = useState<TransformDocumentation | null>(null);
  const [loading, setLoading] = useState(true);
  const [showReadme, setShowReadme] = useState(false);

  // The caller keys this component by transform name, so each transform gets a
  // fresh mount and there is no stale state to reset here.
  useEffect(() => {
    if (!open || !transform) return;
    let cancelled = false;
    api.transforms
      .getDocumentation(transform.name)
      .then((loaded) => {
        if (!cancelled) setDoc(loaded);
      })
      .catch((e) => {
        if (!cancelled) toast.error(`Failed to load transform info: ${String(e)}`);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, transform]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !transform) return null;

  const hasWrittenDocs = Boolean(
    doc && (doc.long_description || doc.when_to_use || doc.limitations || doc.example_use_cases.length > 0)
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl bg-surface border border-border rounded-lg shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`About ${transform.display_name}`}
      >
        <div className="flex items-start justify-between gap-3 px-4 py-3 border-b border-border">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-text">{transform.display_name}</h2>
            <p className="text-[10px] text-text-muted mt-0.5">
              {doc?.category || transform.category}
              {doc?.source === "plugin" && doc.plugin_name
                ? ` · plugin: ${doc.plugin_name}${doc.plugin_version ? ` v${doc.plugin_version}` : ""}`
                : " · built-in"}
            </p>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text shrink-0" aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <div className="p-4 space-y-4 max-h-[70vh] overflow-y-auto">
          {loading && (
            <div className="flex items-center gap-2 text-xs text-text-muted">
              <Loader2 size={12} className="animate-spin" />
              Loading documentation...
            </div>
          )}

          <Section title="What it does">
            <p className="text-xs text-text-muted whitespace-pre-line">
              {doc?.long_description || doc?.description || transform.description}
            </p>
          </Section>

          {doc?.when_to_use && (
            <Section title="When to use it">
              <p className="text-xs text-text-muted whitespace-pre-line">{doc.when_to_use}</p>
            </Section>
          )}

          {doc && doc.example_use_cases.length > 0 && (
            <Section title="Example use cases">
              <ul className="list-disc list-inside space-y-0.5">
                {doc.example_use_cases.map((useCase) => (
                  <li key={useCase} className="text-xs text-text-muted">
                    {useCase}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {doc?.limitations && (
            <Section title="Limitations">
              <p className="text-xs text-warning whitespace-pre-line">{doc.limitations}</p>
            </Section>
          )}

          <Section title="Inputs and outputs">
            <div className="space-y-1">
              <TypeList label="Accepts" types={doc?.input_types ?? transform.input_types} />
              <TypeList label="Produces" types={doc?.output_types ?? transform.output_types} />
            </div>
          </Section>

          {(doc?.api_key_services ?? transform.api_key_services).length > 0 && (
            <Section title="Requirements">
              <p className="text-xs text-warning">
                Needs an API key for: {(doc?.api_key_services ?? transform.api_key_services).join(", ")}
              </p>
              {doc?.source === "plugin" && isUnverifiedTier(doc.plugin_verification_tier) && (
                <p className="text-xs text-amber-300">
                  This plugin is {doc.plugin_verification_tier ?? "community"}-tier and will have access to
                  those keys when it runs.
                </p>
              )}
            </Section>
          )}

          {doc && doc.setting_names.length > 0 && (
            <Section title="Configurable settings">
              <p className="text-xs text-text-muted">{doc.setting_names.join(", ")}</p>
            </Section>
          )}

          {doc && !hasWrittenDocs && !loading && (
            <p className="text-[10px] text-text-muted border-t border-border pt-3">
              This transform has not published detailed documentation yet. Authors can add
              <code className="mx-1 px-1 rounded bg-surface-hover">when_to_use</code>
              and related fields to its manifest.
            </p>
          )}

          {doc?.readme && (
            <div className="border-t border-border pt-3">
              <button
                onClick={() => setShowReadme((v) => !v)}
                className="text-xs text-accent hover:underline flex items-center gap-1"
              >
                <BookOpen size={12} />
                {showReadme ? "Hide full README" : "Show full README"}
              </button>
              {showReadme && (
                <pre className="mt-2 p-2 text-[10px] text-text-muted bg-bg border border-border rounded whitespace-pre-wrap break-words max-h-64 overflow-y-auto">
                  {doc.readme}
                </pre>
              )}
            </div>
          )}
        </div>

        {(doc?.plugin_homepage || doc?.plugin_repository || doc?.plugin_author) && (
          <div className="flex items-center gap-3 px-4 py-2.5 border-t border-border text-[10px] text-text-muted">
            {doc.plugin_author && <span>By {doc.plugin_author}</span>}
            {doc.plugin_homepage && (
              <a
                href={doc.plugin_homepage}
                target="_blank"
                rel="noreferrer noopener"
                className="text-accent hover:underline"
              >
                Homepage
              </a>
            )}
            {doc.plugin_repository && (
              <a
                href={doc.plugin_repository}
                target="_blank"
                rel="noreferrer noopener"
                className="text-accent hover:underline"
              >
                Source
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
