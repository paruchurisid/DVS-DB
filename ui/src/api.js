const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function runQuery(query) {
  const response = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error ?? "Request failed");
  }
  return data;
}

export async function fetchTables() {
  const response = await fetch(`${API_BASE}/tables`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error ?? "Failed to fetch tables");
  }
  return data.tables ?? [];
}

export async function checkpointWal() {
  const response = await fetch(`${API_BASE}/checkpoint`, {
    method: "POST",
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error ?? "Checkpoint failed");
  }
  return data;
}

export async function resetDatabase() {
  const response = await fetch(`${API_BASE}/database`, { method: "DELETE" });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error ?? "Database reset failed");
  }
  return data;
}

export async function uploadCsv({ csvText, tableName, confirm }) {
  const response = await fetch(`${API_BASE}/upload_csv`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      csv_text: csvText,
      table_name: tableName,
      confirm,
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error ?? "CSV upload failed");
  }
  return data;
}
