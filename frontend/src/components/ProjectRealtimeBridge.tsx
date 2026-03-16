import { useCallback, useEffect } from "react";
import { toast } from "sonner";
import { useTransformWebSocket } from "../hooks/useTransformWebSocket";
import { useProjectStore } from "../stores/projectStore";
import { useTransformJobStore } from "../stores/transformJobStore";
import { useInvestigatorStore } from "../stores/investigatorStore";
import { useGraphStore } from "../stores/graphStore";
import type { TransformJobMessage } from "../types/transform";
import type { AgentEventMessage } from "../types/agent";

type ProjectRealtimeMessage = TransformJobMessage | AgentEventMessage | { type: string };

function isTransformMessage(message: ProjectRealtimeMessage): message is TransformJobMessage {
  return "job_id" in message;
}

function isAgentMessage(message: ProjectRealtimeMessage): message is AgentEventMessage {
  return message.type.startsWith("agent_") && "run_id" in message;
}

export function ProjectRealtimeBridge() {
  const currentProject = useProjectStore((state) => state.currentProject);
  const handleTransformMessage = useTransformJobStore((state) => state.handleMessage);
  const handleAgentMessage = useInvestigatorStore((state) => state.handleMessage);
  const applyTransformResult = useGraphStore((state) => state.applyTransformResult);
  const loadGraph = useGraphStore((state) => state.loadGraph);
  const pendingEdgeCount = useGraphStore((state) => state.pendingEdges.size);
  const graphRecovery = useGraphStore((state) => state.graphRecovery);
  const clearGraphRecovery = useGraphStore((state) => state.clearGraphRecovery);

  const onMessage = useCallback(
    (message: ProjectRealtimeMessage) => {
      if (!currentProject) return;

      if (isTransformMessage(message)) {
        handleTransformMessage(message);

        if (message.type === "job_completed" && message.result) {
          applyTransformResult(currentProject.id, message.result);
          toast.success(
            `${message.transform_name}: found ${message.result.entities.length} entities, ${message.result.edges.length} connections`
          );
        }

        if (message.type === "job_failed") {
          toast.error(`${message.transform_name}: ${message.error ?? "Unknown error"}`);
        }

        if (message.type === "job_cancelled") {
          toast.info(`${message.transform_name}: cancelled`);
        }
        return;
      }

      if (isAgentMessage(message)) {
        void handleAgentMessage(currentProject.id, message);
      }
    },
    [applyTransformResult, currentProject, handleAgentMessage, handleTransformMessage]
  );

  useTransformWebSocket({
    projectId: currentProject?.id ?? null,
    onMessage,
  });

  useEffect(() => {
    if (!currentProject || !graphRecovery.reason) return;

    const timeout = window.setTimeout(() => {
      const { pendingEdges } = useGraphStore.getState();
      if (pendingEdges.size === 0) {
        clearGraphRecovery();
        return;
      }
      void loadGraph(currentProject.id);
      toast.info("Refreshing graph to recover from an inconsistent realtime patch");
      clearGraphRecovery();
    }, 1500);

    return () => window.clearTimeout(timeout);
  }, [clearGraphRecovery, currentProject, graphRecovery.nonce, graphRecovery.reason, loadGraph, pendingEdgeCount]);

  return null;
}
