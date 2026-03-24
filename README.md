# DVS-DB (Data Vault by Sid)

**DVS-DB** is a locally running, single-process database system and full-stack interface designed to teach and simulate real database architecture in a hackable, understandable way. It combines a custom embedded storage engine, transactional durability mechanisms, an HTTP API layer, and a browser-based UI into one cohesive workflow.

### Core Features

- **Engine & Storage**
  - File-backed page storage with deterministic fixed-size records
  - B-tree indexing for ordered keys and efficient lookups
  - Serializer enforcing schema and row boundaries
  - Soft-delete support for logical row deletion

- **CRUD & SQL-like Operations**
  - `INSERT`, `SELECT`, `UPDATE`, and `DELETE` (soft-delete) for core tables
  - Key-optimized queries and full-table scans for other filters
  - High-level cursor abstraction (`DVSCursor`) for programmatic transactional operations

- **ACID Transactions (Pragmatic Single-Threaded)**
  - Write-Ahead Log (WAL) with synchronous `fsync` for durability
  - Transactional queueing with `BEGIN -> operation -> COMMIT`
  - Manual checkpoints to flush pages and compact WAL
  - Crash recovery replays committed transactions only

- **Frontend**
  - React + Vite + Tailwind interface
  - Query editor, results table, sidebar table navigation
  - CSV upload with schema inference and dynamic table creation
  - Operational log panel with timestamped, color-coded feedback

- **API**
  - FastAPI endpoints for queries, checkpoints, resets, and CSV ingestion
  - Structured JSON responses with defensive error handling

- **Testing**
  - Unit and integration tests for pager, serializer, B-tree, WAL, checkpoint, API endpoints, CRUD, and cursor transactions

### Quick Start

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Run the API (from the repository root):

```bash
uvicorn api.main:app --reload --port 8000
```

3. Run the web UI:

```bash
cd ui
npm install
npm run dev
```

Open the Vite URL (default `http://localhost:5173`). Point the UI at the API if needed via `ui/.env.local` and `VITE_API_BASE_URL` (for example `http://127.0.0.1:8000`).

4. Run automated tests:

```bash
pytest -q
```

Runtime database files default to `runtime_data/` (`dvsdb.db`, `dvsdb.wal`, `dynamic_tables.json`). They are recreated on first use; delete that folder for a cold start.