import PropTypes from "prop-types";
import shared from "./DataViews.module.css";

/**
 * A captioned table with scoped column headers. Columns render a field by
 * key, or anything through `render(row)`. The caption is a polite live
 * region so a filtered row count is announced.
 */
export default function DataTable({
  columns,
  rows,
  rowKey,
  caption,
  emptyMessage = "Nothing to show.",
  labelledBy,
  minWidth,
}) {
  return (
    <div className={shared.tableWrapper}>
      <table
        className={shared.table}
        aria-labelledby={labelledBy}
        style={minWidth ? { minWidth } : undefined}
      >
        <caption role="status" aria-live="polite">
          {caption}
        </caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col">
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className={shared.muted}>
                {emptyMessage}
              </td>
            </tr>
          )}
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.key}>
                  {column.render
                    ? column.render(row)
                    : (row[column.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

DataTable.propTypes = {
  columns: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string.isRequired,
      header: PropTypes.node.isRequired,
      render: PropTypes.func,
    }),
  ).isRequired,
  rows: PropTypes.array.isRequired,
  rowKey: PropTypes.func.isRequired,
  caption: PropTypes.node.isRequired,
  emptyMessage: PropTypes.node,
  labelledBy: PropTypes.string,
  minWidth: PropTypes.number,
};
