import { Shield, ShieldCheck, Users, FlaskConical } from "lucide-react";
import { VERIFICATION_TIERS } from "../../types/registry";
import type { VerificationTier } from "../../types/registry";

interface VerificationBadgeProps {
  tier: VerificationTier;
  size?: "sm" | "md";
}

const TIER_CONFIG: Record<VerificationTier, { label: string; color: string; bg: string; Icon: typeof Shield }> = {
  [VERIFICATION_TIERS.OFFICIAL]: {
    label: "Official",
    color: "text-blue-400",
    bg: "bg-blue-400/10",
    Icon: ShieldCheck,
  },
  [VERIFICATION_TIERS.VERIFIED]: {
    label: "Verified",
    color: "text-green-400",
    bg: "bg-green-400/10",
    Icon: Shield,
  },
  [VERIFICATION_TIERS.COMMUNITY]: {
    label: "Community",
    color: "text-text-muted",
    bg: "bg-surface",
    Icon: Users,
  },
  [VERIFICATION_TIERS.EXPERIMENTAL]: {
    label: "Experimental",
    color: "text-yellow-400",
    bg: "bg-yellow-400/10",
    Icon: FlaskConical,
  },
};

export function VerificationBadge({ tier, size = "sm" }: VerificationBadgeProps) {
  const config = TIER_CONFIG[tier] ?? TIER_CONFIG[VERIFICATION_TIERS.COMMUNITY];
  const { label, color, bg, Icon } = config;
  const iconSize = size === "sm" ? 10 : 12;
  const textSize = size === "sm" ? "text-[10px]" : "text-xs";

  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded ${bg} ${color} ${textSize}`}>
      <Icon size={iconSize} />
      {label}
    </span>
  );
}
