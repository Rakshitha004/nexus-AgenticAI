"""
Shared utility functions for the Column Pruning Agent.
Provides column schema fetching from the PostgreSQL database.
"""
import os
import sqlite3


# ──────────────────────────────────────────────────────────────────────────
# The columns that a user cares about when asking about results from the
# Postgres database.  These come from the real underlying tables:
#   aiml_academic.student_semester_results   → SGPA, percentage, grand total
#   aiml_academic.student_subject_results    → per-subject marks / grades
#   aiml_academic.session_subjects           → subject codes / labels
#   aiml_academic.students                   → student USN and name
#   aiml_academic.result_sessions            → session metadata
# We combine the most useful columns into one flat "virtual" list so the
# pruning agent can select the ones relevant to a query.
# ──────────────────────────────────────────────────────────────────────────
_POSTGRES_RESULT_COLUMNS = [
    # Student identity
    "student_usn",
    "student_name",
    # Semester-level aggregates
    "semester_no",
    "sgpa",
    "percentage",
    "grand_total",
    # Per-subject detail
    "subject_code",
    "subject_label",
    "numeric_marks",
    "grade_text",
    "raw_result",
    "result_kind",
    # Session metadata
    "session_id",
    "session_label",
    "source_file_name",
    "study_year",
    "source_folder_year",
    "result_scale",
]


def fetch_table_columns(table_name: str) -> list[str]:
    """Fetch column names for a specific table from the Postgres or SQLite database."""
    # ── SQLite path ──────────────────────────────────────────────────────
    if table_name and table_name.startswith("sqlite://"):
        real_name = table_name.replace("sqlite://", "", 1).strip()
        return _fetch_sqlite_columns(real_name)

    # ── Postgres path ────────────────────────────────────────────────────
    # First, check if it's a known session slug
    session_id, view_type = _resolve_session_from_slug(table_name)
    if session_id:
        view_name = "v_student_subject_results" if view_type == "subject" else "v_student_semester_summary"
        schema_cols = _fetch_postgres_columns(f"aiml_academic.{view_name}")
        if schema_cols:
            return schema_cols

    # Direct table name fetch
    real_cols = _fetch_postgres_columns(table_name)
    if real_cols:
        return real_cols

    # Slug fallback
    return _POSTGRES_RESULT_COLUMNS[:]


def fetch_table_data(table_name: str, columns: list[str], query: str = "", limit: int = 15) -> list[dict]:
    """Fetch actual data rows for the matched table and pruned columns, respecting query filters."""
    if not columns:
        return []

    # Extract simple filters (e.g., "below 8 sgpa")
    filters_sql, params = _extract_numeric_filters(query, columns)

    # ── SQLite path ──────────────────────────────────────────────────────
    if table_name and table_name.startswith("sqlite://"):
        real_name = table_name.replace("sqlite://", "", 1).strip()
        return _fetch_sqlite_data(real_name, columns, filters_sql, params, limit)

    # ── Postgres path ────────────────────────────────────────────────────
    return _fetch_postgres_data(table_name, columns, filters_sql, params, limit)


def _resolve_session_from_slug(table_id: str) -> tuple[int | None, str]:
    """Helper to find session_id and suggest view type from a table slug."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from table_agent.ranker import _database_url
    except ImportError:
        return None, "semester"

    url = _database_url()
    if not url:
        return None, "semester"

    try:
        import re
        conn = psycopg2.connect(url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT session_id, source_relative_path, source_file_name FROM aiml_academic.result_sessions")
                for s in cur.fetchall():
                    rel = (s["source_relative_path"] or s["source_file_name"] or "").strip()
                    slug = "aiml_" + re.sub(r"[^a-zA-Z0-9]+", "_", rel.replace("\\", "/")).strip("_").lower()
                    if slug == table_id or f"session_{s['session_id']}" in table_id:
                        # Determine if we should favor subject view
                        vtype = "subject" if "result" in table_id.lower() or "marks" in table_id.lower() else "semester"
                        return s["session_id"], vtype
        finally:
            conn.close()
    except Exception:
        pass
    return None, "semester"


def _extract_numeric_filters(query: str, available_columns: list[str]) -> tuple[str, list]:
    """Heuristic: extract simple 'column < value' filters from the natural language query."""
    if not query:
        return "", []

    import re
    q = query.lower()
    filters = []
    params = []
    seen_columns = set()

    # Mapping common names to actual DB columns
    mappings = [
        ("percentage", ["percentage"]),
        ("sgpa", ["sgpa"]),
        ("cgpa", ["sgpa"]), 
        ("marks", ["numeric_marks", "grand_total"]),
        ("score", ["numeric_marks", "sgpa"]),
        ("grade", ["grade_text"]),
    ]

    ops = {
        r"\b(?:below|under|less than|<)\b": "<",
        r"\b(?:above|over|greater than|>)\b": ">",
        r"\b(?:equal to|=)\b": "=",
    }

    for op_regex, op_sql in ops.items():
        match = re.search(rf"{op_regex}\s*(\d*\.?\d+)", q)
        if match:
            val = float(match.group(1))
            target_col = None
            for key, col_list in mappings:
                if key in q or any(c in q for c in col_list):
                    valid_cols = [c for c in col_list if c in available_columns]
                    if valid_cols:
                        target_col = valid_cols[0]
                        break
            
            if not target_col and "sgpa" in available_columns and val <= 10:
                target_col = "sgpa"
            
            if target_col and target_col not in seen_columns:
                filters.append(f'"{target_col}" {op_sql} %s')
                params.append(val)
                seen_columns.add(target_col)
            break
    
    return (" AND ".join(filters), params) if filters else ("", [])


def _fetch_postgres_data(table_id: str, columns: list[str], filter_sql: str, params: list, limit: int) -> list[dict]:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from table_agent.ranker import _database_url
    except ImportError:
        return []

    url = _database_url()
    if not url: return []

    session_id, _ = _resolve_session_from_slug(table_id)

    try:
        conn = psycopg2.connect(url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if session_id is None:
                    # Direct table/view name (if schema supplied)
                    if "." in table_id:
                        col_list = ", ".join([f'"{c}"' for c in columns])
                        where = f" WHERE {filter_sql}" if filter_sql else ""
                        cur.execute(f'SELECT {col_list} FROM {table_id}{where} LIMIT %s', (*params, limit))
                        return list(cur.fetchall())
                    return []

                # Use academic views
                subject_cols = {"subject_code", "subject_label", "numeric_marks", "grade_text", "raw_result", "result_kind"}
                use_subject_view = any(c in subject_cols for c in columns)
                view_name = "v_student_subject_results" if use_subject_view else "v_student_semester_summary"
                
                cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_schema='aiml_academic' AND table_name=%s", (view_name,))
                view_cols = {r["column_name"] for r in cur.fetchall()}
                actual_query_cols = [c for c in columns if c in view_cols]
                
                if not actual_query_cols:
                    actual_query_cols = ["student_usn", "student_name"] 
                
                col_sql = ", ".join([f'"{c}"' for c in actual_query_cols])
                final_where = f"session_id = %s"
                if filter_sql:
                    final_where += f" AND {filter_sql}"
                
                cur.execute(f'SELECT {col_sql} FROM aiml_academic.{view_name} WHERE {final_where} LIMIT %s', (session_id, *params, limit))
                return list(cur.fetchall())
        finally:
            conn.close()
    except Exception as e:
        print(f"[column_pruning] Postgres data fetch failed: {e}")
        return []


def _fetch_sqlite_data(table_name: str, columns: list[str], filter_sql: str, params: list, limit: int) -> list[dict]:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "API_Integrations", "nexus_chat.sqlite")
    if not os.path.exists(db_path): return []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        col_sql = ", ".join([f'"{c}"' for c in columns])
        sqlite_filter = filter_sql.replace("%s", "?")
        where = f" WHERE {sqlite_filter}" if sqlite_filter else ""
        cur.execute(f'SELECT {col_sql} FROM "{table_name}"{where} LIMIT ?', (*params, limit))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[column_pruning] SQLite data error: {e}")
        return []


def _fetch_postgres_columns(table_name: str) -> list[str]:
    try:
        import psycopg2
        from table_agent.ranker import _database_url
    except ImportError:
        return []

    url = _database_url()
    if not url: return []

    try:
        conn = psycopg2.connect(url)
        try:
            with conn.cursor() as cur:
                if "." in table_name:
                    schema, tbl = table_name.split(".", 1)
                    cur.execute("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position
                    """, (schema, tbl))
                else:
                    cur.execute("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = %s ORDER BY ordinal_position
                    """, (table_name,))
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"[column_pruning] Postgres column fetch failed for '{table_name}': {e}")
        return []


def _fetch_sqlite_columns(table_name: str) -> list[str]:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "API_Integrations", "nexus_chat.sqlite")
    if not os.path.exists(db_path): return []

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(f'PRAGMA table_info("{table_name}")')
        cols = [row[1] for row in cur.fetchall()]
        conn.close()
        return cols
    except Exception:
        return []
