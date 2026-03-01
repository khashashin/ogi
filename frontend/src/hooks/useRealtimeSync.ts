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
          const { addEntity, graph, entities } = useGraphStore.getState();
          if (payload.eventType === "INSERT") {
            const entity = payload.new as unknown as Entity;
            if (!entities.has(entity.id)) {
              addEntity(projectId, entity);
            }
          } else if (payload.eventType === "DELETE") {
            const old = payload.old as { id?: string };
            if (old.id && graph.hasNode(old.id)) {
              // Remove directly from graph — don't call API delete again
              graph.dropNode(old.id);
              entities.delete(old.id);
              useGraphStore.setState({
                graph,
                entities: new Map(entities),
              });
            }
          } else if (payload.eventType === "UPDATE") {
            const entity = payload.new as unknown as Entity;
            entities.set(entity.id, entity);
            if (graph.hasNode(entity.id)) {
              graph.setNodeAttribute(entity.id, "label", entity.value);
            }
            useGraphStore.setState({ entities: new Map(entities) });
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
          const { addEdge, graph, edges } = useGraphStore.getState();
          if (payload.eventType === "INSERT") {
            const edge = payload.new as unknown as Edge;
            if (!edges.has(edge.id)) {
              addEdge(projectId, edge);
            }
          } else if (payload.eventType === "DELETE") {
            const old = payload.old as { id?: string };
            if (old.id && graph.hasEdge(old.id)) {
              graph.dropEdge(old.id);
              edges.delete(old.id);
              useGraphStore.setState({
                graph,
                edges: new Map(edges),
              });
            }
          } else if (payload.eventType === "UPDATE") {
            const edge = payload.new as unknown as Edge;
            edges.set(edge.id, edge);
            if (graph.hasEdge(edge.id)) {
              graph.setEdgeAttribute(edge.id, "label", edge.label);
            }
            useGraphStore.setState({ edges: new Map(edges) });
          }
        },
      )
      .subscribe();

    return () => {
      supabase!.removeChannel(channel);
    };
  }, [projectId]);
}
