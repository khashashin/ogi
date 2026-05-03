import { create } from "zustand";
import { api } from "../api/client";
import type {
  RegistryTransform,
  RegistryIndex,
  PluginInfo,
  PluginApiKeyUsageReportItem,
  UpdateCheckItem,
} from "../types/registry";

interface RegistryState {
  // Data
  index: RegistryIndex | null;
  installedPlugins: PluginInfo[];
  pluginApiKeyUsageReport: PluginApiKeyUsageReportItem[];
  availableUpdates: UpdateCheckItem[];
  searchResults: RegistryTransform[];
  canManage: boolean;

  // UI state
  loading: boolean;
  installing: string | null;
  updating: string | null;
  toggling: string | null;
  error: string | null;
  searchQuery: string;
  selectedCategory: string | null;
  selectedTier: string | null;
  activeTab: "enabled" | "catalog";

  // Actions
  fetchIndex: () => Promise<void>;
  fetchInstalledPlugins: () => Promise<void>;
  fetchPluginApiKeyUsageReport: () => Promise<void>;
  fetchAvailableUpdates: () => Promise<void>;
  searchTransforms: (query: string, category?: string, tier?: string) => Promise<void>;
  installTransform: (transform: RegistryTransform) => Promise<void>;
  updateTransform: (slug: string) => Promise<void>;
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
  pluginApiKeyUsageReport: [],
  availableUpdates: [],
  searchResults: [],
  canManage: false,
  loading: false,
  installing: null,
  updating: null,
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
      const plugins = await api.plugins.list() as PluginInfo[];
      set({ installedPlugins: plugins });
    } catch {
      set({ installedPlugins: [] });
    }
  },

  fetchPluginApiKeyUsageReport: async () => {
    if (!get().canManage) {
      set({ pluginApiKeyUsageReport: [] });
      return;
    }
    try {
      const report = await api.plugins.apiKeyUsageReport();
      set({ pluginApiKeyUsageReport: report });
    } catch {
      set({ pluginApiKeyUsageReport: [] });
    }
  },

  fetchAvailableUpdates: async () => {
    if (!get().canManage) {
      set({ availableUpdates: [] });
      return;
    }
    try {
      const updates = await api.registry.checkUpdates();
      set({ availableUpdates: updates });
    } catch {
      set({ availableUpdates: [] });
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

  installTransform: async (transform: RegistryTransform) => {
    if (!get().canManage) {
      set({ error: "Only admins can install transforms." });
      return;
    }
    set({ installing: transform.slug, error: null });
    try {
      await api.registry.install(transform.slug);
      // Refresh installed list and search results
      await get().fetchInstalledPlugins();
      await get().fetchPluginApiKeyUsageReport();
      await get().fetchAvailableUpdates();
      const { searchQuery, selectedCategory, selectedTier } = get();
      await get().searchTransforms(searchQuery, selectedCategory ?? undefined, selectedTier ?? undefined);
      set({ installing: null });
    } catch (err) {
      set({ error: (err as Error).message, installing: null });
    }
  },

  updateTransform: async (slug: string) => {
    if (!get().canManage) {
      set({ error: "Only admins can update transforms." });
      return;
    }
    set({ updating: slug, error: null });
    try {
      await api.registry.update(slug);
      await get().fetchInstalledPlugins();
      await get().fetchPluginApiKeyUsageReport();
      await get().fetchAvailableUpdates();
      const { searchQuery, selectedCategory, selectedTier } = get();
      await get().searchTransforms(searchQuery, selectedCategory ?? undefined, selectedTier ?? undefined);
      set({ updating: null });
    } catch (err) {
      set({ error: (err as Error).message, updating: null });
    }
  },

  enablePlugin: async (name: string) => {
    set({ toggling: name, error: null });
    try {
      await api.plugins.enable(name);
      await get().fetchInstalledPlugins();
      await get().fetchPluginApiKeyUsageReport();
      await get().fetchAvailableUpdates();
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
      await get().fetchPluginApiKeyUsageReport();
      await get().fetchAvailableUpdates();
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
