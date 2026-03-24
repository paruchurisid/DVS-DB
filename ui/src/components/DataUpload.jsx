import { useState } from "react";
import { runQuery } from "../api";
import { generateCsvTemplate } from "../utils/csvTemplate";

function escapeSqlString(value) {
  return String(value).replace(/"/g, '\\"');
}

function buildInsertQuery({ id, username, email }) {
  return `INSERT INTO users VALUES (${id}, "${escapeSqlString(username)}", "${escapeSqlString(email)}");`;
}

function parseCsv(text, columns) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const header = columns.join(",").toLowerCase();
  const dataLines = lines[0]?.toLowerCase().replace(/\s+/g, "") === header.replace(/\s+/g, "") ? lines.slice(1) : lines;

  return dataLines.map((line) => {
    const [id, username, email] = line.split(",").map((part) => part?.trim() ?? "");
    return { id, username, email };
  });
}

export default function DataUpload({ onInsertSuccess, columns = ["id", "username", "email"] }) {
  const [id, setId] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [downloadStatus, setDownloadStatus] = useState("");

  function validateFields(row) {
    if (!row.id || !row.username || !row.email) {
      return "All fields are required";
    }
    if (!/^\d+$/.test(String(row.id))) {
      return "id must be a valid number";
    }
    return "";
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const row = { id: id.trim(), username: username.trim(), email: email.trim() };
    const validationError = validateFields(row);
    if (validationError) {
      setStatus(validationError);
      return;
    }

    setLoading(true);
    setStatus("");
    try {
      await runQuery(buildInsertQuery(row));
      setStatus("Row inserted successfully");
      setId("");
      setUsername("");
      setEmail("");
      onInsertSuccess?.();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Insert failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleCsvUpload(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setLoading(true);
    setStatus("");
    try {
      const csvText = await file.text();
      const rows = parseCsv(csvText, columns);
      if (!rows.length) {
        throw new Error("CSV file is empty");
      }

      let inserted = 0;
      for (const row of rows) {
        const validationError = validateFields(row);
        if (validationError) {
          throw new Error(`CSV row ${inserted + 1}: ${validationError}`);
        }
        await runQuery(buildInsertQuery(row));
        inserted += 1;
      }
      setStatus(`Inserted ${inserted} row(s) successfully`);
      onInsertSuccess?.();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "CSV upload failed");
    } finally {
      setLoading(false);
      event.target.value = "";
    }
  }

  function handleDownloadTemplate() {
    const csv = generateCsvTemplate(columns);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "sample_users.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    setDownloadStatus("Sample CSV downloaded");
  }

  return (
    <section className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">Data Upload</h3>
      <form className="grid grid-cols-1 gap-3 md:grid-cols-3" onSubmit={handleSubmit}>
        <input
          type="text"
          value={id}
          onChange={(event) => setId(event.target.value)}
          placeholder="id"
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
          disabled={loading}
        />
        <input
          type="text"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="username"
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
          disabled={loading}
        />
        <input
          type="text"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="email"
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
          disabled={loading}
        />
        <div className="md:col-span-3 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {loading ? "Inserting..." : "Insert Row"}
          </button>
          <label className="text-sm text-slate-600">
            <span className="mr-2 font-medium">CSV upload:</span>
            <input type="file" accept=".csv,text/csv" onChange={handleCsvUpload} disabled={loading} />
          </label>
        </div>
        <div className="md:col-span-3 rounded-md border border-slate-200 bg-white p-3 text-sm">
          <p className="font-medium text-slate-700">Use Table Row Template</p>
          <p className="mt-1 text-slate-500">Download a template CSV to match the required format.</p>
          <p className="mt-2 font-mono text-xs text-slate-600">{columns.join(",")}</p>
          <button
            type="button"
            onClick={handleDownloadTemplate}
            disabled={loading}
            className="mt-3 rounded-md border border-slate-300 bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Download Sample CSV
          </button>
          {downloadStatus ? <p className="mt-2 text-xs text-emerald-700">{downloadStatus}</p> : null}
        </div>
      </form>
      <div className="mt-3 text-sm">
        {status ? (
          <span className={status.toLowerCase().includes("success") || status.toLowerCase().includes("inserted") ? "text-emerald-700" : "text-red-600"}>
            {status}
          </span>
        ) : (
          <span className="text-slate-500">Tip: CSV format is id,username,email per line.</span>
        )}
      </div>
    </section>
  );
}
