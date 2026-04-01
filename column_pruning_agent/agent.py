"""
ColumnPruningAgent — BaseAgent wrapper for integration into the Nexus dispatcher.

Wraps the logic from `column pruning/column_agent.py` so it can be registered
with the Intent_Agent3 dispatcher and respond to chat messages.

Chat behaviour:
  - If the message contains a list of columns (comma/newline separated on the
    second line) it will prune them using the offline heuristic (no LLM / API key needed).
  - Otherwise it explains what the agent does and how to use it.

The full LLM-powered pruning (with GOOGLE_API_KEY) is exposed via a dedicated
FastAPI router — see column_pruning_router.py.
"""
import sys
import os
import sqlite3
import asyncio

# Make sure the sibling "column pruning" folder is importable
_CP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "column pruning")
if _CP_DIR not in sys.path:
    sys.path.insert(0, _CP_DIR)

from Intent_Agent3.base import BaseAgent, Message  # noqa: E402
from .utils import fetch_table_columns, fetch_table_data


HELP_TEXT = (
    "I am the **Column Pruning Agent**.\n\n"
    "I automatically find the best matching table in your database and prune its columns based on your query.\n\n"
    "**Example Queries:**\n"
    "- 'prune columns for 3rd sem results'\n"
    "- 'filter features for academic year 2023'\n\n"
    "For the full LLM-powered experience with visual results, visit /column-pruning."
)


class ColumnPruningAgent(BaseAgent):

    def __init__(self):
        super().__init__("column_pruning_agent")
        self._agent = None  # lazy-load

    def _get_agent(self):
        if self._agent is None:
            try:
                from column_agent import ColumnPruningAgent as _CPA  # from column pruning/
                self._agent = _CPA()
            except Exception:
                self._agent = None
        return self._agent

    async def handle_message(self, message: Message) -> Message:
        query = message.text.strip()
        
        # 1. Rank tables
        try:
            from table_agent.ranker import rank_tables
        except ImportError:
            return Message(sender="column_pruning_agent", text="Internal error: Could not import TableAgent ranker.")

        tables, err = await asyncio.to_thread(rank_tables, query, top_k=1)
        if err or not tables:
            return Message(
                sender="column_pruning_agent", 
                text=f"I couldn't find a matching database table for your query. {err or ''}\n\n{HELP_TEXT}"
            )
        
        top_table = tables[0]
        table_id = top_table["table_id"]
        table_alias = top_table["table"]

        # 2. Fetch Columns
        db_type = top_table.get("db_type", "postgres")
        # Ensure we use the source_file (sqlite://Prefix) if it's a local DB
        lookup_id = top_table.get("source_file") if db_type == "sqlite" else table_id
        
        try:
            columns = await asyncio.to_thread(fetch_table_columns, lookup_id)
        except Exception as e:
            return Message(sender="column_pruning_agent", text=f"Error fetching database columns: {e}")

        if not columns:
            return Message(sender="column_pruning_agent", text=f"The matched table '{table_alias}' seems to have no columns.")

        # 3. Prune
        agent = self._get_agent()
        has_key = bool(os.getenv("GOOGLE_API_KEY", "").strip())

        try:
            if agent is None:
                # Fallback to very simple keyword match
                q_low = query.lower()
                kept = [c for c in columns if c.lower() in q_low or any(t in c.lower() for t in q_low.split())]
                if not kept: kept = columns[:5]
                reasons = {c: "Keyword match" for c in kept}
            elif not has_key:
                # Offline heuristic
                kept = await asyncio.to_thread(agent.prune_offline_simple, query, columns)
                reasons = {c: "Heuristic match" for c in kept}
            else:
                # LLM
                kept, reasons, _ = await asyncio.to_thread(agent.prune_with_reason, query, columns)

            dropped = [c for c in columns if c not in kept]
            
            # 4. Fetch actual data rows (passed query for smart filtering)
            data_rows = await asyncio.to_thread(fetch_table_data, lookup_id, kept, query=query, limit=15)
            
            data_md = ""
            if data_rows:
                headers = list(data_rows[0].keys())
                header_row = "| " + " | ".join(headers) + " |"
                sep_row = "| " + " | ".join(["---"] * len(headers)) + " |"
                body_rows = []
                for row in data_rows:
                    body_rows.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
                
                data_md = f"\n\n### 📊 Data Preview (Top {len(data_rows)})\n\n{header_row}\n{sep_row}\n" + "\n".join(body_rows)
            else:
                data_md = "\n\n_(No records found matching this session in the database.)_"

            response = (
                f"🎯 **Matched Table:** {table_alias} (`{table_id}`)\n\n"
                f"✅ **Keep ({len(kept)}/{len(columns)}):** {', '.join(kept)}\n"
                f"❌ **Drop:** {', '.join(dropped) if dropped else 'none'}\n\n"
                f"**Reasoning Sample:** {next(iter(reasons.values())) if reasons else 'N/A'}"
                f"{data_md}\n\n"
                f"_Visit /column-pruning for the full visual breakdown._"
            )

            return Message(
                sender="column_pruning_agent",
                text=response,
                metadata={"kept": kept, "dropped": dropped, "table": table_id},
            )

        except Exception as e:
            return Message(sender="column_pruning_agent", text=f"Error during pruning: {e}")

