import { memo, useState } from "react";
import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import { DAG_STATUS_COLORS, type DagJobNodeData } from "@/utils/dagLayout";

function DagJobNodeInner({ data }: NodeProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const nodeData = data as unknown as DagJobNodeData;
  const colors = DAG_STATUS_COLORS[nodeData.status] ?? DAG_STATUS_COLORS.unknown;

  return (
    <div
      className={`dag-job-node${nodeData.isRoot ? " dag-job-node--root" : ""}${nodeData.isCriticalPath ? " dag-job-node--critical" : ""}`}
      style={{
        background: colors.bg,
        borderColor: nodeData.isRoot ? "#2563eb" : colors.border,
        borderWidth: nodeData.isRoot ? 2.5 : 1.5,
      }}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="dag-handle dag-handle--target"
      />

      <div className="dag-job-node__content">
        <div className="dag-job-node__name" title={nodeData.label}>
          {nodeData.label.length > 22 ? nodeData.label.slice(0, 20) + "\u2026" : nodeData.label}
        </div>
        <div className="dag-job-node__meta">
          <span
            className="dag-job-node__status-badge"
            style={{ background: colors.badge }}
          />
          <span className="dag-job-node__status-text">{nodeData.status}</span>
          <span className="dag-job-node__type">{nodeData.jobType}</span>
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="dag-handle dag-handle--source"
      />

      {showTooltip && (
        <div className="dag-job-tooltip" role="tooltip">
          <div className="dag-job-tooltip__row">
            <strong>Job:</strong> {nodeData.label}
          </div>
          <div className="dag-job-tooltip__row">
            <strong>Status:</strong> {nodeData.status}
          </div>
          <div className="dag-job-tooltip__row">
            <strong>Type:</strong> {nodeData.jobType}
          </div>
          <div className="dag-job-tooltip__hint">Click to view job details</div>
        </div>
      )}
    </div>
  );
}

const DagJobNode = memo(DagJobNodeInner);
export default DagJobNode;
