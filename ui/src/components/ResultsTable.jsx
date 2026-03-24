export default function ResultsTable({ columns, rows }) {
  if (!columns.length) {
    return <div className="text-sm text-slate-500">Run a query to see results.</div>;
  }

  return (
    <div className="overflow-auto rounded-md border border-slate-200 bg-white">
      <table className="min-w-full border-collapse text-left text-sm">
        <thead className="bg-slate-50">
          <tr>
            {columns.map((column) => (
              <th key={column} className="border-b border-slate-200 px-3 py-2 font-semibold text-slate-700">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={`row-${rowIndex}`} className="hover:bg-slate-50">
              {row.map((value, cellIndex) => (
                <td key={`cell-${rowIndex}-${cellIndex}`} className="border-b border-slate-100 px-3 py-2 text-slate-700">
                  {String(value)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <div className="p-3 text-sm text-slate-500">(No rows)</div>}
    </div>
  );
}
