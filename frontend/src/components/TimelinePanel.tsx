import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Pause, Play, RotateCcw } from "lucide-react";

import { api } from "../api/client";
import { useProjectStore } from "../stores/projectStore";
import { useGraphStore } from "../stores/graphStore";
import type { TimelineBucket, TimelineResponse } from "../types/timeline";

function formatBucketLabel(iso: string, interval: "minute" | "hour" | "day" | "week"): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  if (interval === "minute") return d.toLocaleString();
  if (interval === "hour") return d.toLocaleString();
  return d.toLocaleDateString();
}

export function TimelinePanel() {
  const { currentProject } = useProjectStore();
  const { loadGraphWindow, loadGraph, setCenterView } = useGraphStore();
  const [interval, setIntervalValue] = useState<"minute" | "hour" | "day" | "week">("day");
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  const projectId = currentProject?.id ?? null;
  const buckets = timeline?.buckets ?? [];
  const maxCount = Math.max(1, ...buckets.map((b) => b.count));

  const selectedBucket: TimelineBucket | null = useMemo(() => {
    if (selectedIndex == null) return null;
    return buckets[selectedIndex] ?? null;
  }, [buckets, selectedIndex]);

  const refresh = async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.timeline.get(projectId, interval);
      setTimeline(data);
      setSelectedIndex(null);
      await loadGraph(projectId);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, interval]);

  useEffect(() => {
    if (!playing || !projectId || buckets.length === 0) return;
    timerRef.current = window.setInterval(async () => {
      setSelectedIndex((prev) => {
        const next = prev == null ? 0 : prev + 1;
        if (next >= buckets.length) {
          setPlaying(false);
          return null;
        }
        return next;
      });
    }, 1000);
    return () => {
      if (timerRef.current != null) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [playing, projectId, buckets.length]);

  useEffect(() => {
    if (!projectId) return;
    setCenterView("graph");
    if (!selectedBucket) {
      void loadGraph(projectId);
      return;
    }
    void loadGraphWindow(projectId, selectedBucket.bucket_start, selectedBucket.bucket_end);
  }, [selectedBucket, projectId, setCenterView, loadGraphWindow, loadGraph]);

  useEffect(() => {
    return () => {
      if (projectId) {
        void loadGraph(projectId);
      }
    };
  }, [projectId, loadGraph]);

  if (!projectId) {
    return <div className="h-full p-3 text-xs text-text-muted">Select a project to view timeline.</div>;
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">Interval</span>
          <select
            value={interval}
            onChange={(e) => setIntervalValue(e.target.value as "minute" | "hour" | "day" | "week")}
            className="rounded border border-border bg-surface px-2 py-1 text-xs text-text"
          >
            <option value="minute">Minute</option>
            <option value="hour">Hour</option>
            <option value="day">Day</option>
            <option value="week">Week</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPlaying((v) => !v)}
            disabled={loading || buckets.length === 0}
            className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-[11px] text-text-muted hover:text-text hover:bg-surface-hover disabled:opacity-60"
          >
            {playing ? <Pause size={12} /> : <Play size={12} />}
            {playing ? "Pause" : "Play"}
          </button>
          <button
            onClick={() => setSelectedIndex(null)}
            disabled={loading}
            className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-[11px] text-text-muted hover:text-text hover:bg-surface-hover disabled:opacity-60"
          >
            <RotateCcw size={12} />
            Reset
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-3 mt-2 rounded border border-red-500/40 bg-red-500/10 px-2 py-1 text-[11px] text-red-300">
          {error}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-3">
        {loading ? (
          <div className="flex h-full items-center justify-center text-xs text-text-muted">
            <Loader2 size={14} className="mr-2 animate-spin" />
            Loading timeline...
          </div>
        ) : buckets.length === 0 ? (
          <div className="text-xs text-text-muted">No timeline data yet.</div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-12 items-end gap-1 rounded border border-border bg-bg/50 p-2">
              {buckets.map((bucket, idx) => {
                const h = Math.max(8, Math.round((bucket.count / maxCount) * 80));
                const active = selectedIndex === idx;
                return (
                  <button
                    key={`${bucket.bucket_start}-${idx}`}
                    onClick={() => setSelectedIndex(idx)}
                    title={`${formatBucketLabel(bucket.bucket_start, interval)} (${bucket.count})`}
                    className={`rounded-t transition-colors ${active ? "bg-accent" : "bg-surface-hover hover:bg-accent/70"}`}
                    style={{ height: `${h}px` }}
                  />
                );
              })}
            </div>

            <div className="rounded border border-border bg-bg/50 p-2 text-[11px] text-text-muted">
              <div>Total events: <span className="text-text">{timeline?.total_events ?? 0}</span></div>
              <div>Buckets: <span className="text-text">{buckets.length}</span></div>
              {selectedBucket ? (
                <>
                  <div>Selected window: <span className="text-text">{formatBucketLabel(selectedBucket.bucket_start, interval)} - {formatBucketLabel(selectedBucket.bucket_end, interval)}</span></div>
                  <div>Bucket events: <span className="text-text">{selectedBucket.count}</span></div>
                  <div className="mt-1">Event types:</div>
                  <pre className="overflow-x-auto text-[10px]">{JSON.stringify(selectedBucket.event_types, null, 2)}</pre>
                </>
              ) : (
                <div className="mt-1">Select a bucket to filter graph by time window.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
