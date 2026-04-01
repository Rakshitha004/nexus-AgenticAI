"""
FastAPI router for the Column Pruning Agent.

POST /column-pruning/prune-columns
  - Accepts: form-data/JSON with `query` and `use_llm`
  - Uses table_agent to rank and find the best database table.
  - Queries Postgres for the schema columns of that table.
  - Prunes columns using the agent (LLM or fallback).
"""
import sys
import os
import json

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse

from .utils import fetch_table_columns

# Make sure sister folders are importable
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CP_DIR = os.path.join(_REPO_ROOT, "column pruning")

if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
if _CP_DIR not in sys.path:
    sys.path.insert(0, _CP_DIR)

router = APIRouter()



@router.post("/prune-columns")
async def prune_columns(
    query: str = Form(..., description="Natural language query"),
    use_llm: bool = Form(False, description="Use LLM reasoning (requires GOOGLE_API_KEY)"),
):
    """
    Prune columns from a database table based on a natural language query.
    This dynamically queries the TableAgent ranker to find matching tables,
    and then prunes the columns of the top matched table.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # 1. Ask TableAgent to find the most relevant database table
    try:
        from table_agent.ranker import rank_tables
    except ImportError:
        raise HTTPException(status_code=500, detail="Could not import TableAgent ranker.")

    tables, err = rank_tables(query, top_k=1)
    if err or not tables:
        raise HTTPException(
            status_code=404, 
            detail=f"Could not find any database tables for your query (err: {err}). Please refine your query (e.g. '3rd sem')."
        )
    
    top_table = tables[0]
    table_id = top_table["table_id"]
    table_alias = top_table["table"]
    db_type = top_table.get("db_type", "postgres")
    
    # If the match was from SQLite, use the source_file (e.g. sqlite://Semester)
    # so fetch_table_columns knows to skip postgres connection attempts.
    lookup_id = top_table.get("source_file") if db_type == "sqlite" else table_id

    # 2. Extract column definitions
    try:
        columns = fetch_table_columns(lookup_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not columns:
        raise HTTPException(
            status_code=404, 
            detail=f"Table '{table_id}' was found, but it has no columns or doesn't physically exist in the database."
        )

    # 3. Initialize Agent
    has_key = bool(os.getenv("GOOGLE_API_KEY", "").strip())
    use_llm_actual = use_llm and has_key
    agent = None

    try:
        from column_agent import ColumnPruningAgent
        agent = ColumnPruningAgent()
    except ImportError:
        use_llm_actual = False

    # 4. Prune the database columns
    try:
        if agent is None or not use_llm_actual:
            # Offline heuristic
            if agent:
                kept = agent.prune_offline_simple(query, columns)
                reasons = {c: "Selected by heuristic keyword match against the query." for c in kept}
            else:
                q = query.lower()
                tokens = set(q.split())
                kept = [c for c in columns if any(t in c.lower() for t in tokens)]
                if not kept:
                    kept = columns[:5]
                reasons = {c: "Heuristic fallback." for c in kept}
            
            dropped = [c for c in columns if c not in kept]
            mode_used = "offline_heuristic"
            llm_available = has_key and agent is not None
        else:
            # Full LLM reasoning
            kept, reasons, dropped = agent.prune_with_reason(query, columns)
            mode_used = "llm_reasoning"
            llm_available = True

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Column pruning failed: {e}")

    total = len(columns)
    n_kept = len(kept)
    n_dropped = total - n_kept

    return JSONResponse({
        "query": query,
        "matched_table": table_id,
        "matched_table_alias": table_alias,
        "mode": mode_used,
        "llm_available": llm_available,
        "total_columns": total,
        "kept_count": n_kept,
        "dropped_count": n_dropped,
        "reduction_pct": round(n_dropped / total * 100, 1) if total else 0,
        "kept": kept,
        "dropped": dropped,
        "reasons": reasons,
        # Remove file data preview since we're using database tables now
        "preview_columns": None, 
    })


@router.get("/status")
def column_pruning_status():
    """Health/capability check for the column pruning agent."""
    has_key = bool(os.getenv("GOOGLE_API_KEY", "").strip())

    try:
        from column_agent import ColumnPruningAgent  # noqa
        agent_ok = True
    except ImportError:
        agent_ok = False

    try:
        from table_agent.ranker import _database_url
        import psycopg2
        db_ok = True
    except ImportError:
        db_ok = False

    return {
        "status": "ok",
        "agent": "column_pruning_agent",
        "google_api_key_set": has_key,
        "llm_mode_available": has_key and agent_ok,
        "database_connected": db_ok,
        "offline_heuristic_available": agent_ok,
    }
