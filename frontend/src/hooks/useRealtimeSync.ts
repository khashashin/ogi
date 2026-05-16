import { useEffect } from "react";
import { supabase } from "../lib/supabase";
import { useGraphStore } from "../stores/graphStore";
import type { Entity } from "../types/entity";
import type { Edge } from "../types/edge";
import type { RealtimePostgresChangesPayload } from "@supabase/supabase-js";

/**
 * Subscribe to Supabase Realtime Postgres Changes for a project.
 * When entities/edges are inserted, updated, or deleted by another user,
 * the local Graphology graph is updated in real time.
 *
 * No-op when Supabase is not configured.
 */
export function useRealtimeSync(projectId: string | null) {
  useEffect(() => {
    if (!supabase || !projectId) return;

    const applyRealtimeEntity = (entity: Entity) => {
      useGraphStore.getState().upsertEntities(projectId, [entity]);
    };

    const applyRealtimeEdge = (edge: Edge) => {
      useGraphStore.getState().upsertEdges(projectId, [edge]);
    };

    const channel = supabase
      .channel(`project:${projectId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "entities",
          filter: `project_id=eq.${projectId}`,
        },
        (payload: RealtimePostgresChangesPayload<Record<string, unknown>>) => {
          if (payload.eventType === "INSERT") {
            const entity = payload.new as unknown as Entity;
            applyRealtimeEntity(entity);
          } else if (payload.eventType === "DELETE") {
            const old = payload.old as { id?: string };
            if (old.id) {
              useGraphStore.getState().removeEntityLocal(projectId, old.id);
            }
          } else if (payload.eventType === "UPDATE") {
            const entity = payload.new as unknown as Entity;
            applyRealtimeEntity(entity);
          }
        },
      )
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "edges",
          filter: `project_id=eq.${projectId}`,
        },
        (payload: RealtimePostgresChangesPayload<Record<string, unknown>>) => {
          if (payload.eventType === "INSERT") {
            const edge = payload.new as unknown as Edge;
            applyRealtimeEdge(edge);
          } else if (payload.eventType === "DELETE") {
            const old = payload.old as { id?: string };
            if (old.id) {
              useGraphStore.getState().removeEdgeLocal(projectId, old.id);
            }
          } else if (payload.eventType === "UPDATE") {
            const edge = payload.new as unknown as Edge;
            applyRealtimeEdge(edge);
          }
        },
      )
      .subscribe();

    return () => {
      supabase!.removeChannel(channel);
    };
  }, [projectId]);
}
