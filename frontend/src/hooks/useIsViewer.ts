import { useProjectStore } from "../stores/projectStore";

export function useIsViewer(): boolean {
  return useProjectStore((s) => s.currentProject?.role === "viewer");
}
