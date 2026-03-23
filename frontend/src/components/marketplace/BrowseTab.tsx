import { useState, useEffect, useCallback } from "react";
import { Search } from "lucide-react";
import { TransformCard } from "./TransformCard";
import { TransformDetail } from "./TransformDetail";
import { CategoryFilter } from "./CategoryFilter";
import { useRegistryStore } from "../../stores/registryStore";
import type { RegistryTransform } from "../../types/registry";

export function BrowseTab() {
  const {
    searchResults,
    loading,
    installing,
    toggling,
    canManage,
    searchQuery,
    selectedCategory,
    selectedTier,
    installedPlugins,
    searchTransforms,
    installTransform,
    enablePlugin,
    disablePlugin,
    setSelectedCategory,
    setSelectedTier,
  } = useRegistryStore();

  const [localQuery, setLocalQuery] = useState(searchQuery);
  const [selectedTransform, setSelectedTransform] = useState<RegistryTransform | null>(null);

  const doSearch = useCallback(() => {
    searchTransforms(localQuery, selectedCategory ?? undefined, selectedTier ?? undefined);
  }, [localQuery, selectedCategory, selectedTier, searchTransforms]);

  useEffect(() => {
    doSearch();
  }, [selectedCategory, selectedTier]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      doSearch();
    }
  };

  const pluginBySlug = new Map(installedPlugins.map((plugin) => [plugin.name, plugin]));

  if (selectedTransform) {
    const installedPlugin = pluginBySlug.get(selectedTransform.slug);
    return (
      <div className="flex-1 overflow-y-auto p-1">
        <TransformDetail
          transform={selectedTransform}
          available={Boolean(installedPlugin)}
          enabled={Boolean(installedPlugin?.enabled)}
          canManage={canManage}
          installing={installing === selectedTransform.slug}
          toggling={toggling === selectedTransform.slug}
          onInstall={() => installTransform(selectedTransform.slug)}
          onEnable={() => enablePlugin(selectedTransform.slug)}
          onDisable={() => disablePlugin(selectedTransform.slug)}
          onBack={() => setSelectedTransform(null)}
        />
      </div>
    );
  }

  return (
    <div className="flex gap-3 flex-1 min-h-0">
      {/* Category sidebar */}
      <CategoryFilter
        transforms={searchResults}
        selectedCategory={selectedCategory}
        onSelectCategory={setSelectedCategory}
        selectedTier={selectedTier}
        onSelectTier={setSelectedTier}
      />

      {/* Main content */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Search bar */}
        <div className="relative mb-2">
          <Search
            size={12}
            className="absolute left-2 top-1/2 -translate-y-1/2 text-text-muted"
          />
          <input
            type="text"
            value={localQuery}
            onChange={(e) => setLocalQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            placeholder="Search transforms..."
            className="w-full pl-7 pr-3 py-1.5 text-xs bg-bg border border-border rounded text-text placeholder:text-text-muted focus:outline-none focus:border-accent"
          />
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto space-y-2">
          {loading && (
            <p className="text-xs text-text-muted p-2">Loading...</p>
          )}
          {!loading && searchResults.length === 0 && (
            <p className="text-xs text-text-muted p-2">
              No transforms found. Try a different search query.
            </p>
          )}
          {searchResults.map((t) => {
            const installedPlugin = pluginBySlug.get(t.slug);
            return (
              <TransformCard
                key={t.slug}
                transform={t}
                available={Boolean(installedPlugin)}
                enabled={Boolean(installedPlugin?.enabled)}
                canManage={canManage}
                installing={installing === t.slug}
                toggling={toggling === t.slug}
                onInstall={() => installTransform(t.slug)}
                onEnable={() => enablePlugin(t.slug)}
                onDisable={() => disablePlugin(t.slug)}
                onClick={() => setSelectedTransform(t)}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
