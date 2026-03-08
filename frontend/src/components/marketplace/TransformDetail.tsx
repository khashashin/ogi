import { AlertTriangle, ArrowLeft, ExternalLink, Key, ShieldAlert, Tag } from "lucide-react";
import { VerificationBadge } from "./VerificationBadge";
import { InstallButton } from "./InstallButton";
import type { RegistryTransform, VerificationTier } from "../../types/registry";
import { hasNetworkAndSecretRisk, isUnverifiedTier } from "../../lib/pluginRisk";

interface TransformDetailProps {
  transform: RegistryTransform;
  available: boolean;
  enabled: boolean;
  canManage: boolean;
  installing: boolean;
  updateAvailable: boolean;
  updating: boolean;
  toggling: boolean;
  onInstall: () => void;
  onUpdate: () => void;
  onEnable: () => void;
  onDisable: () => void;
  onBack: () => void;
}

export function TransformDetail({
  transform,
  available,
  enabled,
  canManage,
  installing,
  updateAvailable,
  updating,
  toggling,
  onInstall,
  onUpdate,
  onEnable,
  onDisable,
  onBack,
}: TransformDetailProps) {
  const pop = transform.popularity;
  const requiredServices = transform.api_keys_required.map((item) => item.service);
  const hasSecretNetworkRisk = hasNetworkAndSecretRisk(requiredServices, transform.permissions);
  const isSecretUsingUnverified =
    requiredServices.length > 0 && isUnverifiedTier(transform.verification_tier);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button
          onClick={onBack}
          className="p-1 text-text-muted hover:text-text rounded hover:bg-surface-hover mt-0.5"
        >
          <ArrowLeft size={14} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-text">
              {transform.display_name || transform.slug}
            </h3>
            <VerificationBadge tier={transform.verification_tier as VerificationTier} size="md" />
            {transform.version && (
              <span className="text-[10px] text-text-muted bg-surface px-1.5 py-0.5 rounded">
                v{transform.version}
              </span>
            )}
          </div>
          <p className="text-xs text-text-muted mt-1">{transform.description}</p>
        </div>
        <InstallButton
          available={available}
          enabled={enabled}
          canManage={canManage}
          bundled={transform.bundled}
          installing={installing}
          updateAvailable={updateAvailable}
          updating={updating}
          toggling={toggling}
          onInstall={onInstall}
          onUpdate={onUpdate}
          onEnable={onEnable}
          onDisable={onDisable}
        />
      </div>

      {(hasSecretNetworkRisk || isSecretUsingUnverified) && (
        <div className="rounded border border-amber-400/20 bg-amber-400/5 px-3 py-2 space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-amber-300 font-medium">
            <AlertTriangle size={12} />
            Secret-use risk
          </div>
          {hasSecretNetworkRisk && (
            <p className="text-[11px] text-text-muted">
              This plugin requests both network access and API keys. Treat it as privileged code.
            </p>
          )}
          {isSecretUsingUnverified && (
            <p className="flex items-center gap-1.5 text-[11px] text-orange-300">
              <ShieldAlert size={11} />
              Trust tier is {transform.verification_tier}. Review the plugin carefully before use.
            </p>
          )}
        </div>
      )}

      {/* Metadata grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div>
          <span className="text-text-muted">Author</span>
          <p className="text-text">
            {transform.author}
            {transform.author_github && (
              <span className="text-text-muted"> (@{transform.author_github})</span>
            )}
          </p>
        </div>
        <div>
          <span className="text-text-muted">Trust tier</span>
          <p className="text-text capitalize">{transform.verification_tier}</p>
        </div>
        <div>
          <span className="text-text-muted">Category</span>
          <p className="text-text capitalize">{transform.category}</p>
        </div>
        <div>
          <span className="text-text-muted">License</span>
          <p className="text-text">{transform.license || "—"}</p>
        </div>
        <div>
          <span className="text-text-muted">Min OpenGraph Intel Version</span>
          <p className="text-text">{transform.min_ogi_version || "—"}</p>
        </div>
        {transform.input_types.length > 0 && (
          <div>
            <span className="text-text-muted">Input types</span>
            <p className="text-text">{transform.input_types.join(", ")}</p>
          </div>
        )}
        {transform.output_types.length > 0 && (
          <div>
            <span className="text-text-muted">Output types</span>
            <p className="text-text">{transform.output_types.join(", ")}</p>
          </div>
        )}
      </div>

      {/* Tags */}
      {transform.tags.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <Tag size={10} className="text-text-muted" />
          {transform.tags.map((tag) => (
            <span
              key={tag}
              className="text-[10px] px-1.5 py-0.5 rounded bg-surface text-text-muted"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* API keys */}
      {transform.api_keys_required.length > 0 && (
        <div className="p-2 rounded bg-yellow-400/5 border border-yellow-400/20">
          <div className="flex items-center gap-1.5 text-xs text-yellow-400 font-medium mb-1">
            <Key size={12} />
            API Keys Required
          </div>
          <p className="text-[10px] text-text-muted ml-4 mb-1">
            Configure these in <span className="text-text">API Keys</span>. Secret-using plugins are privileged code.
          </p>
          {transform.api_keys_required.map((key) => (
            <p key={key.env_var} className="text-[10px] text-text-muted ml-4">
              <code className="text-text">{key.env_var}</code> — {key.description}
            </p>
          ))}
        </div>
      )}

      {/* Dependencies */}
      {transform.python_dependencies.length > 0 && (
        <div>
          <span className="text-xs text-text-muted">Python dependencies</span>
          <p className="text-xs text-text mt-0.5">
            {transform.python_dependencies.join(", ")}
          </p>
        </div>
      )}

      {/* Permissions */}
      <div>
        <span className="text-xs text-text-muted">Permissions</span>
        <div className="flex items-center gap-3 mt-0.5 text-xs">
          <span className={transform.permissions.network ? "text-green-400" : "text-text-muted"}>
            Network: {transform.permissions.network ? "Yes" : "No"}
          </span>
          <span className={transform.permissions.filesystem ? "text-yellow-400" : "text-text-muted"}>
            Filesystem: {transform.permissions.filesystem ? "Yes" : "No"}
          </span>
          <span className={transform.permissions.subprocess ? "text-red-400" : "text-text-muted"}>
            Subprocess: {transform.permissions.subprocess ? "Yes" : "No"}
          </span>
        </div>
      </div>

      {/* Popularity */}
      {pop && pop.computed_score > 0 && (
        <div className="flex items-center gap-4 text-xs text-text-muted">
          <span>Score: {pop.computed_score}</span>
          <span>+{pop.thumbs_up} / -{pop.thumbs_down}</span>
          <span>{pop.total_contributors} contributors</span>
          {pop.discussion_url && (
            <a
              href={pop.discussion_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-0.5 text-accent hover:underline"
            >
              Discussion <ExternalLink size={10} />
            </a>
          )}
        </div>
      )}

      {/* Links */}
      {transform.readme_url && (
        <a
          href={transform.readme_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
        >
          View README <ExternalLink size={10} />
        </a>
      )}
    </div>
  );
}
