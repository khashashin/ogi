export interface TimelineBucket {
  bucket_start: string;
  bucket_end: string;
  count: number;
  event_types: Record<string, number>;
}

export interface TimelineResponse {
  interval: "minute" | "hour" | "day" | "week";
  window_start?: string | null;
  window_end?: string | null;
  total_events: number;
  buckets: TimelineBucket[];
}
