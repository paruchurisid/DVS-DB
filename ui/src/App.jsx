import { useEffect, useState } from "react";
import { checkpointWal, fetchTables, runQuery } from "./api";
import QueryEditor from "./components/QueryEditor";
import ResultsTable from "./components/ResultsTable";
import RunQueryButton from "./components/RunQueryButton";
import Sidebar from "./components/Sidebar";
import DataUpload from "./components/DataUpload";

function App() {
  const [query, setQuery] = useState("SELECT * FROM users;");
  const [columns, setColumns] = useState([]);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [checkpointLoading, setCheckpointLoading] = useState(false);
  const [tables, setTables] = useState(["users"]);

  useEffect(() => {
    fetchTables()
      .then((names) => {
        if (names.length) {
          setTables(names);
        }
      })
      .catch(() => {
        setTables(["users"]);
      });
  }, []);

  async function onRunQuery() {
    setLoading(true);
    setError("");
    try {
      const result = await runQuery(query);
      setColumns(result.columns ?? []);
      setRows(result.rows ?? []);
    } catch (err) {
      setColumns([]);
      setRows([]);
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function onCheckpointWal() {
    setCheckpointLoading(true);
    setError("");
    try {
      const result = await checkpointWal();
      setError(result.message ?? "WAL checkpoint completed");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Checkpoint failed");
    } finally {
      setCheckpointLoading(false);
    }
  }

  return (
    <div className="grid min-h-screen grid-cols-[240px_1fr]">
      <Sidebar tables={tables} />
      <main className="flex min-h-screen flex-col gap-4 p-5">
        <header>
          <h1 className="text-2xl font-bold text-slate-800">DvsDB Interface</h1>
          <p className="text-sm text-slate-500">React + FastAPI client for the DvsDB embedded engine.</p>
        </header>
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">Query Editor</h2>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onCheckpointWal}
                disabled={checkpointLoading || loading}
                className="rounded-md border border-slate-300 bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {checkpointLoading ? "Checkpointing..." : "Checkpoint WAL"}
              </button>
              <RunQueryButton onClick={onRunQuery} loading={loading} />
            </div>
          </div>
          <QueryEditor query={query} onChange={setQuery} disabled={loading} />
          <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
            {error ? (
              <span className={error.toLowerCase().includes("completed") ? "text-emerald-700" : "text-red-600"}>
                {error.toLowerCase().includes("completed") ? error : `ERROR: ${error}`}
              </span>
            ) : (
              <span className="text-slate-500">Ready.</span>
            )}
          </div>
          <DataUpload onInsertSuccess={onRunQuery} />
        </section>
        <section className="flex-1 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">Results</h2>
          <ResultsTable columns={columns} rows={rows} />
        </section>
      </main>
    </div>
  );
}

export default App;
