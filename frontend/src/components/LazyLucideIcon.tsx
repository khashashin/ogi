import { useEffect, useState } from "react";
import type { ComponentType } from "react";
import { Hash } from "lucide-react";
import type { LucideProps } from "lucide-react";
import dynamicIconImports from "lucide-react/dynamicIconImports";

type DynamicIconModule = {
  default: ComponentType<LucideProps>;
};

const iconComponentCache = new Map<string, ComponentType<LucideProps>>();

function normalizeIconName(iconName: string): string {
  return iconName.trim().toLowerCase();
}

interface LazyLucideIconProps extends LucideProps {
  name: string;
}

export function LazyLucideIcon({ name, ...props }: LazyLucideIconProps) {
  const normalizedName = normalizeIconName(name);
  const [IconComponent, setIconComponent] = useState<ComponentType<LucideProps> | null>(
    () => iconComponentCache.get(normalizedName) ?? null,
  );
  const [resolvedName, setResolvedName] = useState(normalizedName);

  // Sync from cache during render when name changes (React-recommended pattern)
  if (resolvedName !== normalizedName) {
    setResolvedName(normalizedName);
    setIconComponent(iconComponentCache.get(normalizedName) ?? null);
  }

  useEffect(() => {
    if (iconComponentCache.has(normalizedName)) return;

    const importer = dynamicIconImports[normalizedName as keyof typeof dynamicIconImports];
    if (!importer) return;

    let cancelled = false;
    importer().then((module) => {
      if (cancelled) return;
      const resolved = (module as DynamicIconModule).default;
      iconComponentCache.set(normalizedName, resolved);
      setIconComponent(() => resolved);
    });

    return () => {
      cancelled = true;
    };
  }, [normalizedName]);

  if (!IconComponent) return <Hash {...props} />;

  return <IconComponent {...props} />;
}
