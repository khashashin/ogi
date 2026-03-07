import { AlertTriangle, Key, ShieldAlert } from "lucide-react";
import { VerificationBadge } from "./VerificationBadge";
import { InstallButton } from "./InstallButton";
import type { RegistryTransform, VerificationTier } from "../../types/registry";
import { hasNetworkAndSecretRisk, isUnverifiedTier } from "../../lib/pluginRisk";

interface TransformCardProps {
  transform: RegistryTransform;
  available: boolean;
  enabled: boolean;
  canManage: boolean;
  installing: boolean;
  toggling: boolean;
  onInstall: () => void;
  onEnable: () => void;
  onDisable: () => void;
  onClick: () => void;
}

export function TransformCard({
  transform,
  available,
  enabled,
  canManage,
  installing,
  toggling,
  onInstall,
  onEnable,
  onDisable,
  onClick,
}: TransformCardProps) {
  const score = transform.popularity?.computed_score ?? 0;
  const hasSecretNetworkRisk = hasNetworkAndSecretRisk(
    transform.api_keys_required.map((item) => item.service),
    transform.permissions
  );
  const isSecretUsingUnverified =
    transform.api_keys_required.length > 0 && isUnverifiedTier(transform.verification_tier);

  return (
    <div
      className="p-3 rounded bg-bg border border-border hover:border-accent/30 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <VerificationBadge tier={transform.verification_tier as VerificationTier} />
            <span className="text-sm font-medium text-text truncate">
              {transform.display_name || transform.slug}
            </span>
          </div>
          <p className="text-xs text-text-muted mt-0.5 line-clamp-2">
            {transform.description}
          </p>
          <div className="flex items-center gap-3 mt-1.5 text-[10px] text-text-muted">
            <span>
              by {transform.author_github ? `@${transform.author_github}` : transform.author}
            </span>
            {score > 0 && <span>Score: {score}</span>}
            {transform.version && <span>v{transform.version}</span>}
          </div>
          {transform.api_keys_required.length > 0 && (
            <div className="flex items-center gap-1 mt-1 text-[10px] text-yellow-400">
              <Key size={10} />
              Requires API key: {transform.api_keys_required.map((item) => item.service).join(", ")}
            </div>
          )}
          <div className="flex items-center gap-2 mt-1 flex-wrap text-[10px]">
            <span className={transform.permissions.network ? "text-green-400" : "text-text-muted"}>
              Network {transform.permissions.network ? "on" : "off"}
            </span>
            <span className={transform.permissions.filesystem ? "text-yellow-400" : "text-text-muted"}>
              Filesystem {transform.permissions.filesystem ? "on" : "off"}
            </span>
            <span className={transform.permissions.subprocess ? "text-red-400" : "text-text-muted"}>
              Subprocess {transform.permissions.subprocess ? "on" : "off"}
            </span>
          </div>
          {hasSecretNetworkRisk && (
            <div className="flex items-center gap-1 mt-1 text-[10px] text-amber-300">
              <AlertTriangle size={10} />
              Network + secrets: privileged plugin
            </div>
          )}
          {isSecretUsingUnverified && (
            <div className="flex items-center gap-1 mt-1 text-[10px] text-orange-300">
              <ShieldAlert size={10} />
              Unverified plugin will access your API keys at runtime
            </div>
          )}
        </div>
        <div className="flex-shrink-0" onClick={(e) => e.stopPropagation()}>
          <InstallButton
            available={available}
            enabled={enabled}
            canManage={canManage}
            bundled={transform.bundled}
            installing={installing}
            toggling={toggling}
            onInstall={onInstall}
            onEnable={onEnable}
            onDisable={onDisable}
          />
        </div>
      </div>
    </div>
  );
}
