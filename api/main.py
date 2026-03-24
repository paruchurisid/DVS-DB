from __future__ import annotations

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from dvsdb.parser import parse_sql
from dvsdb.query_service import safe_execute_statement
from dvsdb.table import Table

DB_PATH = os.path.join("runtime_data", "dvsdb.db")


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    columns: list[str]
    rows: list[list[object]]


class ErrorResponse(BaseModel):
    error: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    table = Table(DB_PATH)
    app.state.table = table
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
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc


@app.get("/tables")
async def list_tables() -> dict[str, list[str]]:
    return {"tables": ["users"]}


@app.post("/checkpoint", responses={400: {"model": ErrorResponse}})
async def checkpoint_endpoint() -> dict[str, str]:
    try:
        app.state.table.checkpoint_wal()
        return {"status": "ok", "message": "WAL checkpoint completed"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
