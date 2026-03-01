import type { RegistryTransform } from "../../types/registry";

interface CategoryFilterProps {
  transforms: RegistryTransform[];
  selectedCategory: string | null;
  onSelectCategory: (category: string | null) => void;
  selectedTier: string | null;
  onSelectTier: (tier: string | null) => void;
}

const TIER_OPTIONS = [
  { value: "official", label: "Official" },
  { value: "verified", label: "Verified" },
  { value: "community", label: "Community" },
  { value: "experimental", label: "Experimental" },
];

export function CategoryFilter({
  transforms,
  selectedCategory,
  onSelectCategory,
  selectedTier,
  onSelectTier,
}: CategoryFilterProps) {
  // Build category counts from transforms
  const categoryCounts = new Map<string, number>();
  for (const t of transforms) {
    const cat = t.category || "other";
    categoryCounts.set(cat, (categoryCounts.get(cat) ?? 0) + 1);
  }
  const categories = Array.from(categoryCounts.entries()).sort((a, b) => a[0].localeCompare(b[0]));

  return (
    <div className="w-36 flex-shrink-0 space-y-3">
      {/* Categories */}
      <div>
        <h4 className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">
          Categories
        </h4>
        <div className="space-y-0.5">
          <button
            onClick={() => onSelectCategory(null)}
            className={`w-full text-left text-xs px-2 py-1 rounded transition-colors ${
              selectedCategory === null
                ? "bg-accent/10 text-accent"
                : "text-text-muted hover:text-text hover:bg-surface-hover"
            }`}
          >
            All ({transforms.length})
          </button>
          {categories.map(([cat, count]) => (
            <button
              key={cat}
              onClick={() => onSelectCategory(cat === selectedCategory ? null : cat)}
              className={`w-full text-left text-xs px-2 py-1 rounded capitalize transition-colors ${
                selectedCategory === cat
                  ? "bg-accent/10 text-accent"
                  : "text-text-muted hover:text-text hover:bg-surface-hover"
              }`}
            >
              {cat} ({count})
            </button>
          ))}
        </div>
      </div>

      {/* Tiers */}
      <div>
        <h4 className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1.5">
          Tier
        </h4>
        <div className="space-y-0.5">
          {TIER_OPTIONS.map(({ value, label }) => (
            <label
              key={value}
              className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text px-2 py-0.5 cursor-pointer"
            >
              <input
                type="checkbox"
                checked={selectedTier === value}
                onChange={() => onSelectTier(selectedTier === value ? null : value)}
                className="w-3 h-3 rounded border-border"
              />
              {label}
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
