import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { workgroups } from "@/services/api";
import { usePermission } from "@/hooks/usePermission";
import type { WorkgroupResponse } from "@/types/api";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import EmptyState from "@/components/shared/EmptyState";
import { formatDateTime } from "@/utils/format";

export default function WorkgroupsList() {
  const [page, setPage] = useState(1);
  const canCreate = usePermission("admin", "admin");

  const { data, loading, error } = useApi(
    () => workgroups.list(page, 50),
    [page]
  );

  return (
    <div>
      <div className="page-header">
        <h2>Workgroups</h2>
        {canCreate && (
          <Link to="/admin/workgroups/new" className="btn btn-primary">
            Create Workgroup
          </Link>
        )}
      </div>

      {loading && <LoadingSpinner />}
      {error && <div className="form-error">Failed to load workgroups: {error}</div>}
      {data && data.items.length === 0 && (
        <EmptyState title="No workgroups" description="Workgroups organize users and scope permissions to resources." />
      )}
      {data && data.items.length > 0 && (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((wg: WorkgroupResponse) => (
                <tr key={wg.id}>
                  <td>{wg.name}</td>
                  <td>{wg.description ?? "—"}</td>
                  <td>{formatDateTime(wg.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.pages > 1 && (
            <div className="data-table-footer">
              <span>{data.total} workgroup{data.total !== 1 ? "s" : ""}</span>
              <div className="pagination">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
                <span>Page {page} of {data.pages}</span>
                <button disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Next</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
