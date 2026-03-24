import { useState } from "react";
import { uploadCsv } from "../api";

export default function DataUpload({ onStatus, onTablesChanged }) {
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [dynamicTableName, setDynamicTableName] = useState("uploaded_table");
  const [dynamicCsvText, setDynamicCsvText] = useState("");
  const [schemaPreview, setSchemaPreview] = useState(null);

  async function handleDynamicCsvPick(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setStatus("");
    try {
      const text = await file.text();
      setDynamicCsvText(text);
      const preview = await uploadCsv({ csvText: text, tableName: dynamicTableName, confirm: false });
      setSchemaPreview(preview);
      setStatus(`Detected ${preview.row_count} rows. Review schema and confirm.`);
    } catch (error) {
      setSchemaPreview(null);
      setStatus(error instanceof Error ? error.message : "Failed to parse CSV");
    } finally {
      setLoading(false);
      event.target.value = "";
    }
  }

  async function handleCreateFromCsv() {
    if (!dynamicCsvText) {
      setStatus("Upload a CSV file first");
      return;
    }
    setLoading(true);
    setStatus("");
    try {
      const result = await uploadCsv({ csvText: dynamicCsvText, tableName: dynamicTableName, confirm: true });
      setStatus(`Created table '${result.table_name}' and inserted ${result.inserted_rows} rows`);
      setSchemaPreview(null);
      setDynamicCsvText("");
      onTablesChanged?.();
      onStatus?.(`Created table '${result.table_name}'`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "CSV table creation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">Dynamic CSV Ingestion</h3>
      <form className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="md:col-span-3 rounded-md border border-blue-200 bg-blue-50 p-3 text-sm">
          <p className="mt-1 text-slate-600">Upload any CSV file, infer schema, then create a table dynamically.</p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <input
              type="text"
              value={dynamicTableName}
              onChange={(e) => setDynamicTableName(e.target.value)}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
              placeholder="table name (e.g. uploaded_table)"
              disabled={loading}
            />
            <input type="file" accept=".csv,text/csv" onChange={handleDynamicCsvPick} disabled={loading} />
            <button
              type="button"
              onClick={handleCreateFromCsv}
              disabled={loading || !schemaPreview}
              className="rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {loading ? "Processing..." : "Create table with this schema?"}
            </button>
          </div>
          {schemaPreview ? (
            <div className="mt-3 rounded border border-blue-200 bg-white p-2">
              <p className="text-xs font-semibold text-slate-700">Inferred Schema Preview</p>
              <p className="mt-1 text-xs text-slate-600">
                Table: <span className="font-mono">{schemaPreview.table_name}</span>, Rows: {schemaPreview.row_count}
              </p>
              <div className="mt-1 flex flex-wrap gap-2">
                {schemaPreview.columns?.map((col) => (
                  <span key={col.name} className="rounded bg-slate-100 px-2 py-1 text-xs font-mono">
                    {col.name}:{col.type}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </form>
      <div className="mt-3 text-sm">
        {status ? (
          <span
            className={
              /\b(detected|created|inserted|success)\b/i.test(status) ? "text-emerald-700" : "text-red-600"
            }
          >
            {status}
          </span>
        ) : (
          <span className="text-slate-500">Tip: CSV format is id,username,email per line.</span>
        )}
      </div>
    </section>
  );
}
