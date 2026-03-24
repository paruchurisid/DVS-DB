export default function QueryEditor({ query, onChange, disabled }) {
  return (
    <textarea
      value={query}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      className="h-40 w-full resize-y rounded-md border border-slate-300 bg-white p-3 font-mono text-sm text-slate-900 shadow-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200 disabled:bg-slate-100"
      placeholder="SELECT * FROM users;"
      spellCheck={false}
    />
  );
}
