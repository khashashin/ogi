import { create } from "zustand";
import { api } from "../api/client";
import type {
  RegistryTransform,
  RegistryIndex,
  PluginInfoV2,
} from "../types/registry";

interface RegistryState {
  // Data
  index: RegistryIndex | null;
  installedPlugins: PluginInfoV2[];
  searchResults: RegistryTransform[];
  canManage: boolean;

  // UI state
  loading: boolean;
  installing: string | null;
  toggling: string | null;
  error: string | null;
  searchQuery: string;
  selectedCategory: string | null;
  selectedTier: string | null;
  activeTab: "enabled" | "catalog";

  // Actions
  fetchIndex: () => Promise<void>;
  fetchInstalledPlugins: () => Promise<void>;
  searchTransforms: (query: string, category?: string, tier?: string) => Promise<void>;
  installTransform: (slug: string) => Promise<void>;
  enablePlugin: (name: string) => Promise<void>;
  disablePlugin: (name: string) => Promise<void>;
  setSearchQuery: (query: string) => void;
  setSelectedCategory: (category: string | null) => void;
  setSelectedTier: (tier: string | null) => void;
  setActiveTab: (tab: "enabled" | "catalog") => void;
  clearError: () => void;
}

export const useRegistryStore = create<RegistryState>((set, get) => ({
  index: null,
  installedPlugins: [],
  searchResults: [],
  canManage: false,
  loading: false,
  installing: null,
  toggling: null,
  error: null,
  searchQuery: "",
  selectedCategory: null,
  selectedTier: null,
  activeTab: "catalog",

  fetchIndex: async () => {
    set({ loading: true, error: null });
    try {
      const index = await api.registry.index();
      set({ index, canManage: Boolean(index.can_manage), loading: false });
    } catch (err) {
      set({ error: (err as Error).message, loading: false });
    }
  },

  fetchInstalledPlugins: async () => {
    try {
      const plugins = await api.plugins.list() as PluginInfoV2[];
      set({ installedPlugins: plugins });
    } catch {
      set({ installedPlugins: [] });
    }
  },

  searchTransforms: async (query: string, category?: string, tier?: string) => {
    set({ loading: true, error: null, searchQuery: query });
    try {
      const results = await api.registry.search(query, category, tier);
      set({ searchResults: results, loading: false });
    } catch (err) {
      set({ error: (err as Error).message, loading: false });
    }
  },

  installTransform: async (slug: string) => {
    if (!get().canManage) {
      set({ error: "Only admins can install transforms." });
      return;
    }
    set({ installing: slug, error: null });
    try {
      await api.registry.install(slug);
      // Refresh installed list and search results
      await get().fetchInstalledPlugins();
      const { searchQuery, selectedCategory, selectedTier } = get();
      await get().searchTransforms(searchQuery, selectedCategory ?? undefined, selectedTier ?? undefined);
      set({ installing: null });
    } catch (err) {
      set({ error: (err as Error).message, installing: null });
    }
  },

  enablePlugin: async (name: string) => {
    set({ toggling: name, error: null });
    try {
      await api.plugins.enable(name);
      await get().fetchInstalledPlugins();
      set({ toggling: null });
    } catch (err) {
      set({ error: (err as Error).message, toggling: null });
    }
  },

  disablePlugin: async (name: string) => {
    set({ toggling: name, error: null });
    try {
      await api.plugins.disable(name);
      await get().fetchInstalledPlugins();
      set({ toggling: null });
    } catch (err) {
      set({ error: (err as Error).message, toggling: null });
    }
  },

  setSearchQuery: (query: string) => set({ searchQuery: query }),
  setSelectedCategory: (category: string | null) => set({ selectedCategory: category }),
  setSelectedTier: (tier: string | null) => set({ selectedTier: tier }),
  setActiveTab: (tab: "enabled" | "catalog") => set({ activeTab: tab }),
  clearError: () => set({ error: null }),
}));
