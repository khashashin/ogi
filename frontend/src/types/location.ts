export interface LocationSuggestion {
  label: string;
  display_name: string;
  lat: number;
  lon: number;
  source: string;
}

export interface LocationSuggestResponse {
  query: string;
  suggestions: LocationSuggestion[];
  source: string;
  rate_limited: boolean;
  retry_after_seconds: number | null;
}
