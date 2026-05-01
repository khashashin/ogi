import { VERIFICATION_TIERS } from "../types/registry";
import type { RegistryTransform, VerificationTier } from "../types/registry";
import type { TransformInfo } from "../types/transform";

type PermissionShape = {
  network?: boolean;
  filesystem?: boolean;
  subprocess?: boolean;
};

function normalizeTier(tier: string | null | undefined): VerificationTier {
  if (tier === VERIFICATION_TIERS.OFFICIAL || tier === VERIFICATION_TIERS.VERIFIED) {
    return tier;
  }
  if (tier === VERIFICATION_TIERS.EXPERIMENTAL) {
    return tier;
  }
  return VERIFICATION_TIERS.COMMUNITY;
}

export function isUnverifiedTier(tier: string | null | undefined): boolean {
  const normalized = normalizeTier(tier);
  return normalized === VERIFICATION_TIERS.COMMUNITY || normalized === VERIFICATION_TIERS.EXPERIMENTAL;
}

export function hasNetworkAndSecretRisk(
  apiKeyServices: string[],
  permissions: PermissionShape | null | undefined,
): boolean {
  return apiKeyServices.length > 0 && Boolean(permissions?.network);
}

export function formatRequiredServices(apiKeyServices: string[]): string {
  return apiKeyServices.join(", ");
}

export function buildInstallRiskWarning(transform: RegistryTransform): string | null {
  if (!hasNetworkAndSecretRisk(transform.api_keys_required.map((item) => item.service), transform.permissions)) {
    return null;
  }

  const services = formatRequiredServices(transform.api_keys_required.map((item) => item.service));
  return [
    `${transform.display_name || transform.slug} requests network access and API keys (${services}).`,
    "Plugins with both capabilities can misuse or exfiltrate those secrets.",
    "Only install plugins you trust.",
    "",
    "Continue with install?",
  ].join("\n");
}

export function buildRunRiskWarning(transform: TransformInfo): string | null {
  if (!transform.plugin_name || transform.api_key_services.length === 0) {
    return null;
  }
  if (!isUnverifiedTier(transform.plugin_verification_tier)) {
    return null;
  }

  const services = formatRequiredServices(transform.api_key_services);
  const tier = normalizeTier(transform.plugin_verification_tier);
  return [
    `${transform.display_name} comes from the ${tier} trust tier and requires API keys (${services}).`,
    "Running it gives plugin code access to those secrets at runtime.",
    "Proceed only if you trust this plugin.",
    "",
    "Run this transform?",
  ].join("\n");
}
