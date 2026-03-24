const DEFAULT_SAMPLE_ROWS = [
  { id: 1, username: "sid", email: "sid@email.com" },
  { id: 2, username: "jane", email: "jane@email.com" },
];

export function generateCsvTemplate(columns = ["id", "username", "email"], sampleRows = DEFAULT_SAMPLE_ROWS) {
  const header = columns.join(",");
  const body = sampleRows
    .map((row) => columns.map((column) => String(row[column] ?? "")).join(","))
    .join("\n");
  return `${header}\n${body}\n`;
}

