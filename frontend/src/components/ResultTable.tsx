interface ResultTableProps {
  columns: string[];
  rows: unknown[][];
  rowCount: number;
}

export default function ResultTable({ columns, rows, rowCount }: ResultTableProps) {
  if (columns.length === 0 || rows.length === 0) {
    return <p className="text-sm text-gray-500 mt-2">No results.</p>;
  }

  return (
    <div className="mt-3 overflow-x-auto">
      <table className="table-auto w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-100">
            {columns.map((col) => (
              <th
                key={col}
                className="text-left px-3 py-2 border border-gray-200 font-medium text-gray-700 whitespace-nowrap"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIdx) => (
            <tr key={rowIdx} className={rowIdx % 2 === 1 ? "bg-gray-50" : ""}>
              {row.map((cell, cellIdx) => (
                <td
                  key={cellIdx}
                  className="px-3 py-1.5 border border-gray-200 text-gray-800 whitespace-nowrap"
                >
                  {cell === null || cell === undefined ? (
                    <span className="text-gray-400 italic">null</span>
                  ) : (
                    String(cell)
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-gray-400 mt-1">
        Showing {rows.length.toLocaleString()} of {rowCount.toLocaleString()} rows
      </p>
    </div>
  );
}
