/**
 * Reusable DAG canvas component wrapping React Flow.
 * Renders a dependency graph with zoom/pan controls and optional editing.
 */
import { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  type OnConnect,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useNavigate } from "react-router-dom";
import DagJobNode from "./DagJobNode";
import { DAG_STATUS_COLORS, type DagJobNodeData } from "@/utils/dagLayout";

interface DagCanvasProps {
  initialNodes: Node<DagJobNodeData>[];
  initialEdges: Edge[];
  /** Allow interactive edge creation/deletion */
  editable?: boolean;
  /** Called when user connects two nodes (drag from source handle to target) */
  onAddDependency?: (sourceJobId: string, targetJobId: string) => void;
  /** Called when user deletes an edge */
  onRemoveDependency?: (dependencyId: string) => void;
  /** Show minimap */
  showMiniMap?: boolean;
}

const nodeTypes = { dagJobNode: DagJobNode };

export default function DagCanvas({
  initialNodes,
  initialEdges,
  editable = false,
  onAddDependency,
  onRemoveDependency,
  showMiniMap = true,
}: DagCanvasProps) {
  const navigate = useNavigate();
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);

  // Sync when props change (e.g., after adding/removing deps)
  useMemo(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  const onConnect: OnConnect = useCallback(
    (params) => {
      if (!editable || !onAddDependency || !params.source || !params.target) return;
      onAddDependency(params.source, params.target);
    },
    [editable, onAddDependency]
  );

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      navigate(`/jobs/${node.id}`);
    },
    [navigate]
  );

  const onEdgeClick = useCallback(
    (_event: React.MouseEvent, edge: Edge) => {
      if (!editable) return;
      setSelectedEdge((prev) => (prev === edge.id ? null : edge.id));
    },
    [editable]
  );

  const handleDeleteSelectedEdge = useCallback(() => {
    if (!selectedEdge || !onRemoveDependency) return;
    const edge = edges.find((e) => e.id === selectedEdge);
    if (edge?.data?.dependencyId) {
      onRemoveDependency(edge.data.dependencyId as string);
    }
    setSelectedEdge(null);
  }, [selectedEdge, edges, onRemoveDependency]);

  // Style selected edge differently
  const styledEdges = useMemo(
    () =>
      edges.map((e) =>
        e.id === selectedEdge
          ? {
              ...e,
              style: { ...e.style, stroke: "#ef4444", strokeWidth: 3 },
              animated: true,
            }
          : e
      ),
    [edges, selectedEdge]
  );

  const miniMapNodeColor = useCallback((node: Node) => {
    const nodeData = node.data as unknown as DagJobNodeData;
    const colors = DAG_STATUS_COLORS[nodeData.status] ?? DAG_STATUS_COLORS.unknown;
    return colors.border;
  }, []);

  return (
    <div className="dag-canvas">
      <ReactFlow
        nodes={nodes}
        edges={styledEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={editable ? onConnect : undefined}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={3}
        nodesDraggable={false}
        nodesConnectable={editable}
        elementsSelectable={editable}
        proOptions={{ hideAttribution: true }}
      >
        <Controls showInteractive={false} />
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#e2e8f0" />
        {showMiniMap && (
          <MiniMap
            nodeColor={miniMapNodeColor}
            nodeStrokeWidth={2}
            zoomable
            pannable
          />
        )}
      </ReactFlow>

      {editable && selectedEdge && (
        <div className="dag-edge-actions">
          <button
            className="btn btn-danger btn-sm"
            onClick={handleDeleteSelectedEdge}
            aria-label="Remove selected dependency"
          >
            Remove Dependency
          </button>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setSelectedEdge(null)}
          >
            Cancel
          </button>
        </div>
      )}

      {editable && (
        <div className="dag-edit-hint">
          Drag from a node&apos;s right handle to another&apos;s left handle to add a dependency.
          Click an edge to select it for removal.
        </div>
      )}
    </div>
  );
}
