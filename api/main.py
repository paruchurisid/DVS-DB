from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
import re
import time
import gc
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dvsdb.dynamic_tables import DynamicTableStore
from dvsdb.parser import parse_sql
from dvsdb.query_service import safe_execute_statement
from dvsdb.table import Table

logger = logging.getLogger(__name__)

DB_PATH = os.path.join("runtime_data", "dvsdb.db")
WAL_PATH = os.path.join("runtime_data", "dvsdb.wal")
DYNAMIC_TABLES_PATH = os.path.join("runtime_data", "dynamic_tables.json")


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    columns: list[str]
    rows: list[list[object]]


class ErrorResponse(BaseModel):
    error: str


class CsvUploadRequest(BaseModel):
    csv_text: str
    table_name: str = "uploaded_table"
    confirm: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    table = Table(DB_PATH)
    dynamic_store = DynamicTableStore(DYNAMIC_TABLES_PATH)
    app.state.table = table
    app.state.dynamic_store = dynamic_store
    try:
        yield
    finally:
        table.close()


app = FastAPI(title="DvsDB API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


@app.post("/query", response_model=QueryResponse, responses={400: {"model": ErrorResponse}})
async def query_endpoint(payload: QueryRequest) -> QueryResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail={"error": "Query cannot be empty"})
    try:
        statement = parse_sql(query)
        result = safe_execute_statement(app.state.table, statement)
        return QueryResponse(columns=result.columns, rows=result.rows)
    except ValueError as exc:
        try:
            dyn = _handle_dynamic_select(query, app.state.dynamic_store)
        except ValueError as dyn_exc:
            raise HTTPException(status_code=400, detail={"error": str(dyn_exc)}) from dyn_exc
        if dyn is not None:
            return QueryResponse(columns=dyn["columns"], rows=dyn["rows"])
        logger.warning("api.query.invalid query=%s error=%s", query, exc)
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc


@app.get("/tables")
async def list_tables() -> dict[str, list[str]]:
    dynamic = app.state.dynamic_store.list_tables()
    tables: list[str] = []
    # Show users table only when it currently contains visible rows.
    if app.state.table.select_all():
        tables.append("users")
    tables.extend(dynamic)
    return {"tables": tables}


@app.post("/checkpoint", responses={400: {"model": ErrorResponse}})
async def checkpoint_endpoint() -> dict[str, str]:
    try:
        logger.info("api.checkpoint.start")
        app.state.table.checkpoint_wal()
        logger.info("api.checkpoint.success")
        return {"status": "ok", "message": "WAL checkpoint completed"}
    except Exception as exc:
        logger.exception("api.checkpoint.failed")
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc


@app.delete("/database", responses={400: {"model": ErrorResponse}})
async def reset_database_endpoint() -> dict[str, str]:
    global DB_PATH, WAL_PATH
    table: Table | None = getattr(app.state, "table", None)
    if table is not None and table.has_active_transaction:
        raise HTTPException(status_code=400, detail={"error": "Cannot reset while a transaction is active"})
    try:
        logger.info("api.database.reset.start")
        if table is not None:
            table.close()
        gc.collect()
        for path in (DB_PATH, WAL_PATH):
            _safe_delete_file(path)
        app.state.dynamic_store.reset()
        app.state.table = Table(DB_PATH)
        logger.info("api.database.reset.success")
        return {"status": "ok", "message": "Database reset সফল"}
    except PermissionError:
        # If another process keeps handles open, rotate to a fresh DB path so
        # reset still succeeds for the current app instance.
        stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        DB_PATH = os.path.join("runtime_data", f"dvsdb_{stamp}.db")
        WAL_PATH = os.path.join("runtime_data", "dvsdb.wal")
        app.state.dynamic_store.reset()
        app.state.table = Table(DB_PATH)
        logger.warning("api.database.reset.fallback_new_db path=%s", DB_PATH)
        return {"status": "ok", "message": "Database reset সফল"}
    except FileNotFoundError:
        app.state.table = Table(DB_PATH)
        return {"status": "ok", "message": "Database reset সফল"}
    except Exception as exc:
        if getattr(app.state, "table", None) is None:
            app.state.table = Table(DB_PATH)
        logger.exception("api.database.reset.failed")
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc


@app.post("/upload_csv", responses={400: {"model": ErrorResponse}})
async def upload_csv_endpoint(payload: CsvUploadRequest) -> dict[str, object]:
    try:
        logger.info("api.upload_csv.start table=%s confirm=%s", payload.table_name, payload.confirm)
        columns, rows, row_count = app.state.dynamic_store.infer_schema_and_rows(payload.csv_text)
        schema = [{"name": c.name, "type": c.type} for c in columns]
        if not payload.confirm:
            preview = rows[:5]
            return {
                "status": "preview",
                "table_name": payload.table_name,
                "columns": schema,
                "sample_rows": preview,
                "row_count": row_count,
            }

        app.state.dynamic_store.create_or_replace_table(payload.table_name, columns)
        inserted = app.state.dynamic_store.insert_rows(payload.table_name, rows)
        logger.info("api.upload_csv.success table=%s inserted=%d", payload.table_name, inserted)
        return {
            "status": "ok",
            "table_name": payload.table_name,
            "columns": schema,
            "inserted_rows": inserted,
        }
    except Exception as exc:
        logger.exception("api.upload_csv.failed table=%s", payload.table_name)
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("api.unhandled_exception")
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


def _handle_dynamic_select(query: str, store: DynamicTableStore) -> dict[str, object] | None:
    full = re.match(r"^\s*select\s+\*\s+from\s+([a-z_][a-z0-9_]*)\s*;?\s*$", query, flags=re.IGNORECASE)
    if full:
        table_name = full.group(1)
        cols, rows = store.select_all(table_name)
        return {"columns": cols, "rows": rows}

    where = re.match(
        r"^\s*select\s+\*\s+from\s+([a-z_][a-z0-9_]*)\s+where\s+([a-z_][a-z0-9_]*)\s*=\s*(.+?)\s*;?\s*$",
        query,
        flags=re.IGNORECASE,
    )
    if where:
        table_name = where.group(1)
        col = where.group(2)
        raw_val = where.group(3).strip()
        if (raw_val.startswith('"') and raw_val.endswith('"')) or (raw_val.startswith("'") and raw_val.endswith("'")):
            raw_val = raw_val[1:-1]
        cols, rows = store.select_where_eq(table_name, col, raw_val)
        return {"columns": cols, "rows": rows}
    return None


def _safe_delete_file(path: str, attempts: int = 20, delay_seconds: float = 0.15) -> None:
    if not os.path.exists(path):
        return
    last_exc: Exception | None = None
    for _ in range(attempts):
        try:
            os.remove(path)
            return
        except FileNotFoundError:
            return
        except PermissionError as exc:
            last_exc = exc
            time.sleep(delay_seconds)
    if last_exc is not None:
        raise last_exc
