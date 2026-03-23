export const VERIFICATION_TIERS = {
  OFFICIAL: "official",
  VERIFIED: "verified",
  COMMUNITY: "community",
  EXPERIMENTAL: "experimental",
} as const;
export type VerificationTier = typeof VERIFICATION_TIERS[keyof typeof VERIFICATION_TIERS];

export const TRANSFORM_SOURCES = {
  BUNDLED: "bundled",
  REGISTRY: "registry",
  LOCAL: "local",
} as const;
export type TransformSource = typeof TRANSFORM_SOURCES[keyof typeof TRANSFORM_SOURCES];

export interface ApiKeyRequirement {
  service: string;
  description: string;
  env_var: string;
}

export interface TransformPermissions {
  network: boolean;
  filesystem: boolean;
  subprocess: boolean;
}

export interface TransformPopularity {
  thumbs_up: number;
  thumbs_down: number;
  total_contributors: number;
  commits_last_90_days: number;
  discussion_url: string;
  computed_score: number;
}

export interface RegistryTransform {
  slug: string;
  name: string;
  display_name: string;
  description: string;
  version: string;
  author: string;
  author_github: string;
  license: string;
  category: string;
  input_types: string[];
  output_types: string[];
  min_ogi_version: string;
  max_ogi_version: string | null;
  python_dependencies: string[];
  api_keys_required: ApiKeyRequirement[];
  tags: string[];
  verification_tier: VerificationTier;
  bundled: boolean;
  download_url: string;
  readme_url: string;
  sha256: string;
  permissions: TransformPermissions;
  popularity: TransformPopularity;
  icon: string;
  color: string;
  created_at: string;
  updated_at: string;
}

export interface RegistryIndex {
  version: number;
  generated_at: string;
  repo: string;
  transforms: RegistryTransform[];
  can_manage?: boolean;
}

export interface InstalledTransform {
  slug: string;
  version: string;
  category: string;
  verification_tier: VerificationTier;
  installed_at: string;
  sha256: string;
  source: string;
  python_dependencies: string[];
  files: string[];
}

export interface PluginInfoV2 {
  name: string;
  version: string;
  display_name: string;
  description: string;
  author: string;
  enabled: boolean;
  transform_count: number;
  transform_names: string[];
  schema_version: number;
  category: string;
  license: string;
  author_github: string;
  tags: string[];
  input_types: string[];
  output_types: string[];
  min_ogi_version: string;
  verification_tier: VerificationTier;
  api_keys_required: ApiKeyRequirement[];
  python_dependencies: string[];
  permissions: TransformPermissions;
  source: TransformSource;
  icon: string;
  color: string;
}
