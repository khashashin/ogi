import { useCallback } from "react";
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
  const loadGraph = useGraphStore((state) => state.loadGraph);

  const onMessage = useCallback(
    (message: ProjectRealtimeMessage) => {
      if (!currentProject) return;

      if (isTransformMessage(message)) {
        handleTransformMessage(message);

        if (message.type === "job_completed" && message.result) {
          void loadGraph(currentProject.id);
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
    [currentProject, handleAgentMessage, handleTransformMessage, loadGraph]
  );

  useTransformWebSocket({
    projectId: currentProject?.id ?? null,
    onMessage,
  });

  return null;
}
