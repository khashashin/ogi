export type BottomTab =
  | "transforms"
  | "analysis"
  | "events"
  | "timeline"
  | "investigator";

export function tabButtonClass(current: BottomTab, tab: BottomTab) {
  return `px-3 py-1.5 text-xs font-medium transition-colors ${
    current === tab
      ? "text-text border-b-2 border-accent"
      : "text-text-muted hover:text-text"
  }`;
}
