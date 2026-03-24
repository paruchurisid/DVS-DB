export default function Sidebar({ tables }) {
  return (
    <aside className="h-full border-r border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Tables</h2>
      {tables.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-4 text-sm text-slate-500">
          No tables yet
        </div>
      ) : (
        <ul className="space-y-2">
          {tables.map((table) => (
            <li key={table} className="rounded-md bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700">
              {table}
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
