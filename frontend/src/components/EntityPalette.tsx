import { useEffect, useMemo, useRef, useState } from "react";
import type { LucideProps } from "lucide-react";
import {
  User, Globe, Server, Mail, Phone, Building2, Link, AtSign,
  Hash, FileText, MapPin, Network, Wifi, Search, Mailbox,
  HardDrive, Shield, FileCode
} from "lucide-react";
import { EntityType, ENTITY_TYPE_META } from "../types/entity";
import type { EntityTypeMeta } from "../types/entity";
import { api } from "../api/client";
import { useProjectStore } from "../stores/projectStore";
import { useGraphStore } from "../stores/graphStore";
import { useIsViewer } from "../hooks/useIsViewer";
import type { LocationSuggestion } from "../types/location";

const ICON_MAP: Record<string, React.ComponentType<LucideProps>> = {
  user: User,
  globe: Globe,
  server: Server,
  mail: Mail,
  phone: Phone,
  building: Building2,
  link: Link,
  "at-sign": AtSign,
  hash: Hash,
  "file-text": FileText,
  "file-code": FileCode,
  "map-pin": MapPin,
  network: Network,
  wifi: Wifi,
  mailbox: Mailbox,
  "hard-drive": HardDrive,
  shield: Shield,
};

/** Custom SVG icons served from /icons/ */
const CUSTOM_SVG_ICONS = new Set(["subdomain", "nsrecord"]);

const ENTITY_VALUE_PLACEHOLDERS: Partial<Record<EntityType, string>> = {
  [EntityType.Person]: "Enter first and last name",
  [EntityType.Username]: "Enter username or handle",
  [EntityType.Organization]: "Enter organization name",
  [EntityType.Domain]: "Enter domain, e.g. example.com",
  [EntityType.Subdomain]: "Enter subdomain, e.g. api.example.com",
  [EntityType.URL]: "Enter full URL, e.g. https://example.com",
  [EntityType.EmailAddress]: "Enter email address",
  [EntityType.PhoneNumber]: "Enter phone number",
  [EntityType.IPAddress]: "Enter IPv4 or IPv6 address",
  [EntityType.SocialMedia]: "Enter username or social handle",
  [EntityType.Hash]: "Enter file or artifact hash",
  [EntityType.Document]: "Enter document title or URL",
  [EntityType.ASNumber]: "Enter ASN, e.g. AS15169",
  [EntityType.Network]: "Enter network or CIDR, e.g. 192.168.0.0/24",
  [EntityType.MXRecord]: "Enter MX record hostname",
  [EntityType.NSRecord]: "Enter NS record hostname",
  [EntityType.Nameserver]: "Enter nameserver hostname",
  [EntityType.SSLCertificate]: "Enter certificate identifier or subject",
  [EntityType.HTTPHeader]: "Enter header name or raw header",
};

export function EntityPalette() {
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState<EntityType | null>(null);
  const [value, setValue] = useState("");
  const [locationSuggestions, setLocationSuggestions] = useState<LocationSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [suggestHint, setSuggestHint] = useState<string>("");
  const [selectedSuggestion, setSelectedSuggestion] = useState<LocationSuggestion | null>(null);
  const suggestionTimer = useRef<number | null>(null);
  const { currentProject } = useProjectStore();
  const { addEntity } = useGraphStore();
  const isViewer = useIsViewer();
  const isLocationMode = adding === EntityType.Location;
  const valuePlaceholder = adding
    ? (isLocationMode ? "Search location..." : ENTITY_VALUE_PLACEHOLDERS[adding] ?? "Enter value")
    : "Enter value";

  const groupedTypes = useMemo(() => {
    const groups: Record<string, EntityTypeMeta[]> = {};
    for (const meta of Object.values(ENTITY_TYPE_META)) {
      if (search && !meta.type.toLowerCase().includes(search.toLowerCase())) continue;
      if (!groups[meta.category]) groups[meta.category] = [];
      groups[meta.category].push(meta);
    }
    return groups;
  }, [search]);

  const handleAdd = async () => {
    if (!adding || !value.trim() || !currentProject) return;
    try {
      const trimmed = value.trim();
      const properties =
        adding === EntityType.Location && selectedSuggestion && selectedSuggestion.display_name === trimmed
          ? {
              lat: selectedSuggestion.lat,
              lon: selectedSuggestion.lon,
              location_label: selectedSuggestion.display_name,
              geo_confidence: 0.6,
            }
          : undefined;
      const entity = await api.entities.create(currentProject.id, {
        type: adding,
        value: trimmed,
        properties,
      });
      addEntity(currentProject.id, entity);
      setAdding(null);
      setValue("");
      setLocationSuggestions([]);
      setSelectedSuggestion(null);
      setSuggestHint("");
    } catch (e) {
      console.error("Failed to add entity:", e);
    }
  };

  useEffect(() => {
    if (!isLocationMode || !currentProject) {
      setLocationSuggestions([]);
      setLoadingSuggestions(false);
      setSuggestHint("");
      return;
    }
    if (suggestionTimer.current !== null) {
      window.clearTimeout(suggestionTimer.current);
      suggestionTimer.current = null;
    }

    const q = value.trim();
    if (q.length < 3) {
      setLocationSuggestions([]);
      setLoadingSuggestions(false);
      setSuggestHint(q.length === 0 ? "" : "Type at least 3 characters for suggestions.");
      return;
    }

    setLoadingSuggestions(true);
    setSuggestHint("");
    suggestionTimer.current = window.setTimeout(async () => {
      try {
        const resp = await api.locations.suggest(currentProject.id, q, 5);
        setLocationSuggestions(resp.suggestions ?? []);
        if (resp.rate_limited) {
          const retry = resp.retry_after_seconds ?? 60;
          setSuggestHint(`Location search is rate-limited. Try again in ~${retry}s.`);
        } else if ((resp.suggestions ?? []).length === 0) {
          setSuggestHint("No matches found.");
        } else {
          setSuggestHint("");
        }
      } catch {
        setSuggestHint("Location suggestions unavailable right now.");
        setLocationSuggestions([]);
      } finally {
        setLoadingSuggestions(false);
      }
    }, 300);

    return () => {
      if (suggestionTimer.current !== null) {
        window.clearTimeout(suggestionTimer.current);
        suggestionTimer.current = null;
      }
    };
  }, [isLocationMode, value, currentProject]);

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-border">
        <h2 className="text-sm font-semibold text-text mb-2">Entities</h2>
        <div className="relative">
          <Search size={14} className="absolute left-2 top-2.5 text-text-muted" />
          <input
            type="text"
            placeholder="Search types..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-7 pr-2 py-1.5 text-sm bg-surface border border-border rounded text-text placeholder:text-text-muted focus:outline-none focus:border-accent"
          />
        </div>
      </div>

      {!isViewer && adding && (
        <div className="p-3 border-b border-border bg-surface">
          <p className="text-xs text-text-muted mb-1.5">Add {adding}</p>
          <input
            type="text"
            placeholder={valuePlaceholder}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setSelectedSuggestion(null);
            }}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            autoFocus
            className="w-full px-2 py-1.5 text-sm bg-bg border border-border rounded text-text placeholder:text-text-muted focus:outline-none focus:border-accent mb-2"
          />
          {isLocationMode && (
            <div className="mb-2 rounded border border-border bg-bg/60">
              {loadingSuggestions && (
                <p className="px-2 py-1 text-[11px] text-text-muted">Searching...</p>
              )}
              {!loadingSuggestions && suggestHint && (
                <p className="px-2 py-1 text-[11px] text-warning">{suggestHint}</p>
              )}
              {!loadingSuggestions && locationSuggestions.length > 0 && (
                <div className="max-h-36 overflow-y-auto">
                  {locationSuggestions.map((item) => (
                    <button
                      key={`${item.display_name}-${item.lat}-${item.lon}`}
                      onClick={() => {
                        setValue(item.display_name);
                        setSelectedSuggestion(item);
                        setLocationSuggestions([]);
                        setSuggestHint("Coordinates will be attached when you add this entity.");
                      }}
                      className="w-full border-t border-border px-2 py-1 text-left text-[11px] text-text hover:bg-surface-hover first:border-t-0"
                    >
                      {item.display_name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          <div className="flex gap-1.5">
            <button
              onClick={handleAdd}
              className="flex-1 px-2 py-1 text-xs bg-accent text-white rounded hover:bg-accent-hover"
            >
              Add
            </button>
            <button
              onClick={() => {
                setAdding(null);
                setValue("");
                setLocationSuggestions([]);
                setSelectedSuggestion(null);
                setSuggestHint("");
              }}
              className="flex-1 px-2 py-1 text-xs bg-surface border border-border text-text-muted rounded hover:bg-surface-hover"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-2">
        {Object.entries(groupedTypes).map(([category, types]) => (
          <div key={category} className="mb-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted px-1 mb-1">
              {category}
            </p>
            {types.map((meta) => {
              const isCustomSvg = CUSTOM_SVG_ICONS.has(meta.icon);
              const IconComponent = ICON_MAP[meta.icon] ?? Hash;
              return (
                <button
                  key={meta.type}
                  onClick={isViewer ? undefined : () => setAdding(meta.type)}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm text-text transition-colors ${isViewer ? "cursor-default" : "hover:bg-surface-hover"}`}
                >
                  {isCustomSvg ? (
                    <img
                      src={`/icons/${meta.icon}.svg`}
                      alt={meta.type}
                      width={14}
                      height={14}
                      className="shrink-0 invert"
                    />
                  ) : (
                    <IconComponent size={14} className="shrink-0" style={{ color: meta.color }} />
                  )}
                  <span>{meta.type}</span>
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
