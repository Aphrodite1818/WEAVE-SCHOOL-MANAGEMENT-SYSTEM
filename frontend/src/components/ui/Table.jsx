import EmptyState from "../shared/EmptyState";
import LoadingState from "../shared/LoadingState";

function Table({ columns = [], rows = [], emptyText = "No records found.", isLoading = false }) {
  if (isLoading) return <LoadingState label="Loading records..." />;

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="p-0 border-none">
                <div className="p-6 md:p-12 border-none">
                  <EmptyState title="No data found" description={emptyText} />
                </div>
              </td>
            </tr>
          ) : (
            rows.map((row, index) => (
              <tr key={row.id || index}>
                {columns.map((column) => (
                  <td key={column.key} data-label={column.label}>
                    <span>{column.render ? column.render(row) : row[column.key] || "-"}</span>
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default Table;
