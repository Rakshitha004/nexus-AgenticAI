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
    real_cols = _fetch_postgres_columns(table_name)
    if real_cols:
        return real_cols

    # Slug fallback
    return _POSTGRES_RESULT_COLUMNS[:]


def fetch_table_data(table_name: str, columns: list[str], query: str = "", limit: int = 15) -> list[dict]:
    """Fetch actual data rows for the matched table and pruned columns, respecting query filters."""
    if not columns:
        return []

    # Extract simple filters from the query (e.g., "below 8 sgpa")
    filters_sql, params = _extract_numeric_filters(query, columns)

    # ── SQLite path ──────────────────────────────────────────────────────
    if table_name and table_name.startswith("sqlite://"):
        real_name = table_name.replace("sqlite://", "", 1).strip()
        return _fetch_sqlite_data(real_name, columns, filters_sql, params, limit)

    # ── Postgres path ────────────────────────────────────────────────────
    return _fetch_postgres_data(table_name, columns, filters_sql, params, limit)


def _extract_numeric_filters(query: str, available_columns: list[str]) -> tuple[str, list]:
    """Heuristic: extract simple 'column < value' filters from the natural language query."""
    if not query:
        return "", []

    import re
    q = query.lower()
    filters = []
    params = []
    seen_columns = set()

    # Mapping common names to actual DB columns (ordered by specificity)
    mappings = [
        ("percentage", ["percentage"]),
        ("sgpa", ["sgpa"]),
        ("cgpa", ["sgpa"]), # Alias for sgpa in this context
        ("marks", ["numeric_marks", "grand_total"]),
        ("score", ["numeric_marks", "sgpa"]),
        ("grade", ["grade_text"]),
    ]

    # Operators
    ops = {
        r"\b(?:below|under|less than|<)\b": "<",
        r"\b(?:above|over|greater than|>)\b": ">",
        r"\b(?:equal to|=)\b": "=",
    }

    # Iterate through operators first
    for op_regex, op_sql in ops.items():
        # Look for "below 8" or "sgpa below 8"
        match = re.search(rf"{op_regex}\s*(\d*\.?\d+)", q)
        if match:
            val = float(match.group(1))
            
            # Find which column this filter applies to
            target_col = None
            for key, col_list in mappings:
                if key in q or any(c in q for c in col_list):
                    valid_cols = [c for c in col_list if c in available_columns]
                    if valid_cols:
                        target_col = valid_cols[0]
                        break
            
            # If no explicit column found, but we have a match like "< 8",
            # default to 'sgpa' if available and valid looking.
            if not target_col and "sgpa" in available_columns and val <= 10:
                target_col = "sgpa"
            
            if target_col and target_col not in seen_columns:
                filters.append(f'"{target_col}" {op_sql} %s')
                params.append(val)
                seen_columns.add(target_col)
            
            # Only handle one numeric filter per query for this heuristic
            break
    
    if not filters:
        return "", []
    
    return " AND ".join(filters), params


def _fetch_postgres_data(table_id: str, columns: list[str], filter_sql: str, params: list, limit: int) -> list[dict]:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from table_agent.ranker import _database_url
    except ImportError:
        return []

    url = _database_url()
    if not url:
        return []

    try:
        conn = psycopg2.connect(url)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. Identify the session_id from the slug if it's a result table
                cur.execute("SELECT session_id, source_relative_path, source_file_name FROM aiml_academic.result_sessions")
                sessions = cur.fetchall()
                
                import re
                target_sid = None
                for s in sessions:
                    rel = (s["source_relative_path"] or s["source_file_name"] or "").strip()
                    slug = "aiml_" + re.sub(r"[^a-zA-Z0-9]+", "_", rel.replace("\\", "/")).strip("_").lower()
                    if slug == table_id or f"session_{s['session_id']}" in table_id:
                        target_sid = s["session_id"]
                        break
                
                if target_sid is None:
                    # Fallback to direct table name
                    if "." in table_id:
                        col_list = ", ".join([f'"{c}"' for c in columns])
                        where_clause = f" WHERE {filter_sql}" if filter_sql else ""
                        cur.execute(f'SELECT {col_list} FROM {table_id}{where_clause} LIMIT %s', (*params, limit))
                        return list(cur.fetchall())
                    return []

                # 2. Determine view
                subject_cols = {"subject_code", "subject_label", "numeric_marks", "grade_text", "raw_result", "result_kind"}
                use_subject_view = any(c in subject_cols for c in columns)
                view_name = "v_student_subject_results" if use_subject_view else "v_student_semester_summary"
                
                cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_schema='aiml_academic' AND table_name=%s", (view_name,))
                view_cols = {r["column_name"] for r in cur.fetchall()}
                actual_query_cols = [c for c in columns if c in view_cols]
                
                if not actual_query_cols:
                    actual_query_cols = ["student_usn", "student_name"] # fallback
                
                col_sql = ", ".join([f'"{c}"' for c in actual_query_cols])
                final_where = f"session_id = %s"
                if filter_sql:
                    final_where += f" AND {filter_sql}"
                
                cur.execute(f'SELECT {col_sql} FROM aiml_academic.{view_name} WHERE {final_where} LIMIT %s', (target_sid, *params, limit))
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
        
        # SQLite uses ? instead of %s
        sqlite_filter = filter_sql.replace("%s", "?")
        where_clause = f" WHERE {sqlite_filter}" if sqlite_filter else ""
        
        cur.execute(f'SELECT {col_sql} FROM "{table_name}"{where_clause} LIMIT ?', (*params, limit))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[column_pruning] SQLite data error: {e}")
        return []


def _fetch_postgres_columns(table_name: str) -> list[str]:
    """Try to fetch columns for a *real* Postgres table by name."""
    try:
        import psycopg2
        from table_agent.ranker import _database_url
    except ImportError:
        return []

    url = _database_url()
    if not url:
        return []

    try:
        conn = psycopg2.connect(url)
        try:
            with conn.cursor() as cur:
                # Handles plain name or schema.name
                if "." in table_name:
                    schema, tbl = table_name.split(".", 1)
                    cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position
                    """, (schema, tbl))
                else:
                    cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = %s
                        ORDER BY ordinal_position
                    """, (table_name,))
                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"[column_pruning] Postgres column fetch failed for '{table_name}': {e}")
        return []


def _fetch_sqlite_columns(table_name: str) -> list[str]:
    """Internal helper to fetch columns from the local SQLite database."""
    # Use absolute path relative to the project root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "API_Integrations", "nexus_chat.sqlite")

    if not os.path.exists(db_path):
        print(f"[column_pruning] SQLite DB not found at: {db_path}")
        return []

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        # Double-quote identifiers to handle mixed-case names like "Semester"
        cur.execute(f'PRAGMA table_info("{table_name}")')
        rows = cur.fetchall()
        cols = [row[1] for row in rows]
        conn.close()

        if not cols:
            print(f"[column_pruning] No columns for SQLite table '{table_name}'.")
        return cols
    except Exception as e:
        print(f"[column_pruning] SQLite error for '{table_name}': {e}")
        return []
