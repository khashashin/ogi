import { Key } from "lucide-react";
import { VerificationBadge } from "./VerificationBadge";
import { InstallButton } from "./InstallButton";
import type { RegistryTransform, VerificationTier } from "../../types/registry";

interface TransformCardProps {
  transform: RegistryTransform;
  installed: boolean;
  installing: boolean;
  removing: boolean;
  onInstall: () => void;
  onRemove: () => void;
  onClick: () => void;
}

export function TransformCard({
  transform,
  installed,
  installing,
  removing,
  onInstall,
  onRemove,
  onClick,
}: TransformCardProps) {
  const score = transform.popularity?.computed_score ?? 0;

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
              API key needed
            </div>
          )}
        </div>
        <div className="flex-shrink-0" onClick={(e) => e.stopPropagation()}>
          <InstallButton
            installed={installed}
            bundled={transform.bundled}
            installing={installing}
            removing={removing}
            onInstall={onInstall}
            onRemove={onRemove}
          />
        </div>
      </div>
    </div>
  );
}
