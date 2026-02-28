import { useEffect, useRef, useCallback } from "react";
import Sigma from "sigma";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { useGraphStore } from "../stores/graphStore";

export function GraphCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const { graph, selectNode, selectedNodeId } = useGraphStore();

  const initSigma = useCallback(() => {
    if (!containerRef.current) return;

    // Clean up previous instance
    if (sigmaRef.current) {
      sigmaRef.current.kill();
      sigmaRef.current = null;
    }

    if (graph.order === 0) return;

    const renderer = new Sigma(graph, containerRef.current, {
      renderEdgeLabels: true,
      defaultEdgeType: "arrow",
      defaultNodeColor: "#6366f1",
      defaultEdgeColor: "#4b5563",
      labelColor: { color: "#e1e4ed" },
      labelSize: 12,
      labelRenderedSizeThreshold: 6,
    });

    renderer.on("clickNode", ({ node }) => {
      selectNode(node);
    });

    renderer.on("clickStage", () => {
      selectNode(null);
    });

    sigmaRef.current = renderer;

    // Run ForceAtlas2 layout for a short burst
    if (graph.order > 1) {
      forceAtlas2.assign(graph, {
        iterations: 100,
        settings: {
          gravity: 1,
          scalingRatio: 2,
          barnesHutOptimize: graph.order > 50,
        },
      });
    }
  }, [graph, selectNode]);

  useEffect(() => {
    initSigma();
    return () => {
      if (sigmaRef.current) {
        sigmaRef.current.kill();
        sigmaRef.current = null;
      }
    };
  }, [initSigma]);

  // Highlight selected node
  useEffect(() => {
    if (!sigmaRef.current) return;
    const renderer = sigmaRef.current;

    renderer.setSetting("nodeReducer", (node, data) => {
      if (selectedNodeId && node !== selectedNodeId) {
        // Check if neighbor
        const isNeighbor = graph.hasNode(selectedNodeId) && graph.areNeighbors(node, selectedNodeId);
        return {
          ...data,
          color: isNeighbor ? data.color : `${data.color}44`,
          label: isNeighbor ? data.label : "",
        };
      }
      if (node === selectedNodeId) {
        return { ...data, highlighted: true, size: (data.size ?? 8) + 3 };
      }
      return data;
    });

    renderer.setSetting("edgeReducer", (edge, data) => {
      if (selectedNodeId) {
        const src = graph.source(edge);
        const tgt = graph.target(edge);
        if (src !== selectedNodeId && tgt !== selectedNodeId) {
          return { ...data, hidden: true };
        }
      }
      return data;
    });

    renderer.refresh();
  }, [selectedNodeId, graph]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full bg-bg"
      style={{ minHeight: "400px" }}
    />
  );
}
