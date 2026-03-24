import { useEffect, useState } from "react";
import { checkpointWal, fetchTables, resetDatabase, runQuery } from "./api";
import QueryEditor from "./components/QueryEditor";
import ResultsTable from "./components/ResultsTable";
import RunQueryButton from "./components/RunQueryButton";
import Sidebar from "./components/Sidebar";
import DataUpload from "./components/DataUpload";

function App() {
  const [query, setQuery] = useState("SELECT * FROM users;");
  const [columns, setColumns] = useState([]);
  const [rows, setRows] = useState([]);
  const [outputLogs, setOutputLogs] = useState([
    { level: "info", message: "Output log initialized.", ts: new Date().toLocaleTimeString() },
  ]);
  const [loading, setLoading] = useState(false);
  const [checkpointLoading, setCheckpointLoading] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
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

  function appendLog(level, message) {
    const entry = { level, message, ts: new Date().toLocaleTimeString() };
    setOutputLogs((prev) => [entry, ...prev].slice(0, 12));
  }

  async function onRunQuery() {
    setLoading(true);
    try {
      const result = await runQuery(query);
      setColumns(result.columns ?? []);
      setRows(result.rows ?? []);
      appendLog("success", `Query executed. Returned ${result.rows?.length ?? 0} row(s).`);
    } catch (err) {
      setColumns([]);
      setRows([]);
      appendLog("error", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function onCheckpointWal() {
    setCheckpointLoading(true);
    try {
      const result = await checkpointWal();
      appendLog("success", result.message ?? "WAL checkpoint completed");
    } catch (err) {
      appendLog("error", err instanceof Error ? err.message : "Checkpoint failed");
    } finally {
      setCheckpointLoading(false);
    }
  }

  async function onResetDatabase() {
    const ok = window.confirm("This will delete the current database and WAL files. Continue?");
    if (!ok) return;
    setResetLoading(true);
    try {
      const result = await resetDatabase();
      setColumns([]);
      setRows([]);
      setTables(["users"]);
      const names = await fetchTables();
      if (names.length) setTables(names);
      appendLog("success", result.message ?? "Database reset completed");
    } catch (err) {
      appendLog("error", err instanceof Error ? err.message : "Database reset failed");
    } finally {
      setResetLoading(false);
    }
  }

  return (
    <div className="grid min-h-screen grid-cols-[240px_1fr]">
      <Sidebar tables={tables} />
      <main className="flex min-h-screen flex-col gap-4 p-5">
        <header className="rounded-xl border border-slate-200 bg-gradient-to-r from-[#001b44] via-[#012456] to-[#0d3d8f] p-5 text-white shadow-sm">
          <div className="flex flex-wrap items-center gap-4">
            <img
              src="/dvsdb-logo.png"
              alt="DVS-DB Data Vault by Sid"
              className="h-14 w-auto rounded-md border border-white/20 bg-white/5 p-1"
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
            />
            <div>
              <h1 className="text-2xl font-bold tracking-wide">DVS-DB</h1>
              <p className="text-sm text-cyan-100">Data Vault by Sid</p>
            </div>
          </div>
        </header>
        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">Query Editor</h2>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onResetDatabase}
                disabled={resetLoading || checkpointLoading || loading}
                className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm font-medium text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {resetLoading ? "Resetting..." : "Reset Database"}
              </button>
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
          <div className="mt-3 rounded-md border border-slate-700 bg-[#012456] p-3 text-sm text-slate-100 shadow-inner">
            <h3 className="mb-2 font-mono text-xs font-semibold uppercase tracking-wide text-sky-200">Output Log</h3>
            <div className="max-h-40 space-y-1 overflow-y-auto font-mono text-xs leading-5">
              {outputLogs.map((log, index) => (
                <div key={`${log.ts}-${index}`} className="flex gap-2">
                  <span className="text-sky-300">[{log.ts}]</span>
                  <span
                    className={
                      log.level === "error"
                        ? "text-rose-300"
                        : log.level === "success"
                          ? "text-emerald-300"
                          : "text-slate-200"
                    }
                  >
                    {log.level === "error" ? "ERROR" : log.level === "success" ? "OK" : "INFO"}: {log.message}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <DataUpload
            onStatus={(msg) => appendLog("info", msg)}
            onTablesChanged={async () => {
              const names = await fetchTables();
              setTables(names.length ? names : ["users"]);
            }}
          />
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
