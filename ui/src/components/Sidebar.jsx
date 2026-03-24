export default function Sidebar({ tables }) {
  return (
    <aside className="h-full border-r border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Tables</h2>
      <ul className="space-y-2">
        {tables.map((table) => (
          <li key={table} className="rounded-md bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700">
            {table}
          </li>
        ))}
      </ul>
    </aside>
  );
}
