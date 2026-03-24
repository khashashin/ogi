import { useEffect, useState } from "react";
import type { ComponentType } from "react";
import { Hash } from "lucide-react";
import type { LucideProps } from "lucide-react";
import dynamicIconImports from "lucide-react/dynamicIconImports";

type DynamicIconModule = {
  default: ComponentType<LucideProps>;
};

interface AsyncIconState {
  name: string;
  icon: ComponentType<LucideProps>;
}

const iconComponentCache = new Map<string, ComponentType<LucideProps>>();

function normalizeIconName(iconName: string): string {
  return iconName.trim().toLowerCase();
}

interface LazyLucideIconProps extends LucideProps {
  name: string;
}

export function LazyLucideIcon({ name, ...props }: LazyLucideIconProps) {
  const normalizedName = normalizeIconName(name);

  // Read cache synchronously during render (no effect needed for cache hits)
  const cachedIcon = iconComponentCache.get(normalizedName) ?? null;

  const [asyncState, setAsyncState] = useState<AsyncIconState | null>(null);

  useEffect(() => {
    if (iconComponentCache.has(normalizedName)) return;

    const importer = dynamicIconImports[normalizedName as keyof typeof dynamicIconImports];
    if (!importer) return;

    let cancelled = false;
    importer().then((module) => {
      if (cancelled) return;
      const resolved = (module as DynamicIconModule).default;
      iconComponentCache.set(normalizedName, resolved);
      setAsyncState({ name: normalizedName, icon: resolved });
    });

    return () => {
      cancelled = true;
    };
  }, [normalizedName]);

  const IconComponent = cachedIcon ?? (asyncState?.name === normalizedName ? asyncState.icon : null);

  if (!IconComponent) return <Hash {...props} />;

  return <IconComponent {...props} />;
}
