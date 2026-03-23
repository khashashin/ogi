import { createElement } from "react";
import type { ComponentType } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { LucideProps } from "lucide-react";
import * as LucideIcons from "lucide-react";

type IconEntry = {
  name: string;
  component: ComponentType<LucideProps>;
};

const CUSTOM_SVG_ICONS = new Set(["subdomain", "nsrecord"]);

function toKebabCase(value: string): string {
  return value
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1-$2")
    .toLowerCase();
}

function toPascalCase(value: string): string {
  return value
    .split(/[^a-zA-Z0-9]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
}

function isLucideIcon(value: unknown): value is ComponentType<LucideProps> {
  return (
    (typeof value === "function" || typeof value === "object") &&
    value !== null
  );
}

const LUCIDE_ICON_ENTRIES: IconEntry[] = Object.entries(LucideIcons)
  .filter(([exportName, value]) => {
    if (!/^[A-Z]/.test(exportName)) return false;
    if (exportName === "Icon" || exportName === "Icons" || exportName === "createLucideIcon") return false;
    return isLucideIcon(value);
  })
  .map(([exportName, component]) => ({
    name: toKebabCase(exportName),
    component: component as ComponentType<LucideProps>,
  }))
  .sort((a, b) => a.name.localeCompare(b.name));

export const LUCIDE_ICON_NAMES = LUCIDE_ICON_ENTRIES.map((entry) => entry.name);

export const LUCIDE_ICON_MAP: Record<string, ComponentType<LucideProps>> = Object.fromEntries(
  LUCIDE_ICON_ENTRIES.map((entry) => [entry.name, entry.component]),
);

const ICON_NAME_ALIASES: Record<string, string> = {
  "at-sign": "badge-at-sign",
  building: "building-2",
  network: "network",
  "file-text": "file-text",
  "file-code": "file-code-2",
  shield: "shield",
  "shield-alert": "shield-alert",
  "hard-drive": "hard-drive",
  globe: "globe",
  hash: "hash",
  phone: "phone",
  link: "link",
  user: "user",
  mail: "mail",
  server: "server",
  wifi: "wifi",
  mailbox: "mailbox",
  "map-pin": "map-pin",
};

export function isCustomSvgIcon(iconName: string): boolean {
  return CUSTOM_SVG_ICONS.has(iconName);
}

export function getIconComponent(iconName: string): ComponentType<LucideProps> | null {
  const normalizedName = iconName.trim().toLowerCase();
  const resolvedName = ICON_NAME_ALIASES[normalizedName] ?? normalizedName;
  const direct = LUCIDE_ICON_MAP[resolvedName];
  if (direct) return direct;

  const pascalCandidate = toPascalCase(resolvedName);
  const lucideExport = (LucideIcons as Record<string, unknown>)[pascalCandidate];
  if (isLucideIcon(lucideExport)) return lucideExport;

  const iconCandidate = (LucideIcons as Record<string, unknown>)[`${pascalCandidate}Icon`];
  if (isLucideIcon(iconCandidate)) return iconCandidate;

  return null;
}

export function renderLucideIconSvg(
  iconName: string,
  props: LucideProps & { strokeWidth?: number } = {},
): string | null {
  const IconComponent = getIconComponent(iconName);
  if (!IconComponent) return null;
  return renderToStaticMarkup(
    createElement(IconComponent, {
      size: 20,
      color: "currentColor",
      strokeWidth: 2.2,
      ...props,
    }),
  );
}
