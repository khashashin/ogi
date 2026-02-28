export const EntityType = {
  Person: "Person",
  Domain: "Domain",
  IPAddress: "IPAddress",
  EmailAddress: "EmailAddress",
  PhoneNumber: "PhoneNumber",
  Organization: "Organization",
  URL: "URL",
  SocialMedia: "SocialMedia",
  Hash: "Hash",
  Document: "Document",
  Location: "Location",
  ASNumber: "ASNumber",
  Network: "Network",
  MXRecord: "MXRecord",
  NSRecord: "NSRecord",
  Nameserver: "Nameserver",
} as const;

export type EntityType = (typeof EntityType)[keyof typeof EntityType];

export interface EntityTypeMeta {
  type: EntityType;
  icon: string;
  color: string;
  category: string;
}

export const ENTITY_TYPE_META: Record<EntityType, EntityTypeMeta> = {
  [EntityType.Person]: { type: EntityType.Person, icon: "user", color: "#6366f1", category: "People" },
  [EntityType.Domain]: { type: EntityType.Domain, icon: "globe", color: "#22d3ee", category: "Infrastructure" },
  [EntityType.IPAddress]: { type: EntityType.IPAddress, icon: "server", color: "#f59e0b", category: "Infrastructure" },
  [EntityType.EmailAddress]: { type: EntityType.EmailAddress, icon: "mail", color: "#a78bfa", category: "People" },
  [EntityType.PhoneNumber]: { type: EntityType.PhoneNumber, icon: "phone", color: "#34d399", category: "People" },
  [EntityType.Organization]: { type: EntityType.Organization, icon: "building", color: "#fb923c", category: "People" },
  [EntityType.URL]: { type: EntityType.URL, icon: "link", color: "#60a5fa", category: "Infrastructure" },
  [EntityType.SocialMedia]: { type: EntityType.SocialMedia, icon: "at-sign", color: "#f472b6", category: "People" },
  [EntityType.Hash]: { type: EntityType.Hash, icon: "hash", color: "#94a3b8", category: "Forensics" },
  [EntityType.Document]: { type: EntityType.Document, icon: "file-text", color: "#e2e8f0", category: "Forensics" },
  [EntityType.Location]: { type: EntityType.Location, icon: "map-pin", color: "#4ade80", category: "Location" },
  [EntityType.ASNumber]: { type: EntityType.ASNumber, icon: "network", color: "#fbbf24", category: "Infrastructure" },
  [EntityType.Network]: { type: EntityType.Network, icon: "wifi", color: "#38bdf8", category: "Infrastructure" },
  [EntityType.MXRecord]: { type: EntityType.MXRecord, icon: "mail", color: "#c084fc", category: "Infrastructure" },
  [EntityType.NSRecord]: { type: EntityType.NSRecord, icon: "server", color: "#67e8f9", category: "Infrastructure" },
  [EntityType.Nameserver]: { type: EntityType.Nameserver, icon: "server", color: "#2dd4bf", category: "Infrastructure" },
};

export interface Entity {
  id: string;
  type: EntityType;
  value: string;
  properties: Record<string, string | number | boolean | null>;
  icon: string;
  weight: number;
  notes: string;
  tags: string[];
  source: string;
  project_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface EntityCreate {
  type: EntityType;
  value: string;
  properties?: Record<string, string | number | boolean | null>;
  weight?: number;
  notes?: string;
  tags?: string[];
  source?: string;
}

export interface EntityUpdate {
  value?: string;
  properties?: Record<string, string | number | boolean | null>;
  weight?: number;
  notes?: string;
  tags?: string[];
}
