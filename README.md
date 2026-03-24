# DVS-DB

DvsDB is a lightweight embedded database engine inspired by SQLite.
It runs entirely in-process against a single `.db` file and uses only Python's standard library.

## Core Architecture

- `dvsdb/pager.py`: fixed-size page I/O and page cache
- `dvsdb/serializer.py`: fixed-schema row encoding/decoding
- `dvsdb/table.py`: logical table abstraction
- `dvsdb/btree.py`: B-tree storage/index by `id`
- `dvsdb/parser.py`: minimal SQL-like parser
- `dvsdb/engine.py`: execution orchestrator
- `dvsdb/cli.py`: interactive REPL shell
- `dvsdb/query_service.py`: structured query execution for API clients

## Interface Architecture

- `api/main.py`: FastAPI server exposing DvsDB over HTTP
- `ui/`: React (Vite) + Tailwind web client
- Data flow: `React -> FastAPI -> DvsDB engine -> JSON response -> React rendering`

## Row Schema

- `id`: 4-byte unsigned integer
- `username`: 32-byte fixed field
- `email`: 255-byte fixed field

## Usage

Run the shell:

```bash
python -m dvsdb.cli mydata.db
```

Supported commands:

- `INSERT INTO users VALUES (1, 'alice', 'alice@example.com')`
- `SELECT * FROM users`
- `.exit`

## Web Interface

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Start API server:

```bash
uvicorn api.main:app --reload
```

Start frontend:

```bash
cd ui
npm install
npm run dev
```

Then open the Vite URL (default `http://localhost:5173`) and run queries like:

- `SELECT * FROM users;`
- `INSERT INTO users VALUES (1, 'alice', 'alice@example.com');`

## Tests

Run all tests:

```bash
python -m unittest discover -s tests -v
```
