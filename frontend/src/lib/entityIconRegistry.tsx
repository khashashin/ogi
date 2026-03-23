import type { ComponentType } from "react";
import type { LucideProps } from "lucide-react";
import {
  AtSign,
  Building2,
  FileCode2,
  FileText,
  Globe,
  HardDrive,
  Hash,
  Link,
  Mail,
  Mailbox,
  MapPin,
  Network,
  Phone,
  Server,
  Shield,
  ShieldAlert,
  User,
  Wifi,
} from "lucide-react";

const CUSTOM_SVG_ICONS = new Set(["subdomain", "nsrecord"]);

const ICON_NAME_ALIASES: Record<string, string> = {
  building: "building-2",
  "file-code": "file-code-2",
};

const ENTITY_ICON_MAP: Record<string, ComponentType<LucideProps>> = {
  user: User,
  "at-sign": AtSign,
  "shield-alert": ShieldAlert,
  globe: Globe,
  server: Server,
  mail: Mail,
  phone: Phone,
  "building-2": Building2,
  link: Link,
  hash: Hash,
  "file-text": FileText,
  "map-pin": MapPin,
  network: Network,
  wifi: Wifi,
  mailbox: Mailbox,
  "hard-drive": HardDrive,
  shield: Shield,
  "file-code-2": FileCode2,
};

export function isCustomSvgIcon(iconName: string): boolean {
  return CUSTOM_SVG_ICONS.has(iconName);
}

export function resolveEntityIconName(iconName: string): string {
  const normalizedName = iconName.trim().toLowerCase();
  return ICON_NAME_ALIASES[normalizedName] ?? normalizedName;
}

export function getEntityIconComponent(iconName: string): ComponentType<LucideProps> | null {
  return ENTITY_ICON_MAP[resolveEntityIconName(iconName)] ?? null;
}
