from typing import List, Dict, Tuple
import ast
import os
import argparse
from pathlib import Path
import json
import re

from dotenv import load_dotenv

load_dotenv()

class ColumnPruningAgent:
    def __init__(self, model: str | None = None):
        # Prefer env override, then fallback to a broadly available, supported model name
        self.effective_model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")
        self.llm = None
        self.prompt = None

    def _init_llm(self):
        if self.llm is not None:
            return
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.prompts import PromptTemplate
            from langchain_core.output_parsers import StrOutputParser
        except ImportError as e:
            raise ImportError(f"Missing LLM dependencies: {e}. Please install langchain-google-genai.")
            
        self.llm = ChatGoogleGenerativeAI(model=self.effective_model)
        self.prompt = PromptTemplate(
            input_variables=["query", "columns"],
            template=(
                "You are a Column Pruning Agent. Your job is to choose only the necessary "
                "columns required to answer the user's query.\n\n"
                "User Query:\n{query}\n\n"
                "Available Columns:\n{columns}\n\n"
                "Rules:\n"
                "- Select only columns needed to answer the query.\n"
                "- Do not add imaginary fields.\n"
                "- Do not include irrelevant or sensitive columns unless the query requires them.\n"
                "- Choose ONLY from the Available Columns using their exact names.\n"
                "- Final output must be ONLY a Python list of column names, with no explanation.\n"
            ),
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def prune_with_reason(self, query: str, columns: List[str]) -> Tuple[List[str], Dict[str, str], List[str]]:
        """Return pruned columns, reasons per column, and pruned-out columns.

        LLM is asked to produce strict JSON: {"keep": [..], "prune": [..], "reasons": {col: reason}}
        """
        self._init_llm()
        from langchain_core.prompts import PromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        
        reason_prompt = PromptTemplate(
            input_variables=["query", "columns"],
            template=(
                "You are a Column Pruning Agent. Choose only necessary columns to answer the query.\n\n"
                "User Query:\n{query}\n\n"
                "Available Columns (use exact names):\n{columns}\n\n"
                "Rules:\n"
                "- Only choose from Available Columns.\n"
                "- No imaginary fields.\n"
                "- Be minimal but sufficient.\n\n"
                "Output STRICT JSON with keys: keep (list of columns to keep), prune (list to drop), reasons (object mapping each column to a short reason).\n"
                "Example: {\"keep\":[\"G3\",\"sex\"],\"prune\":[\"age\"],\"reasons\":{\"G3\":\"target metric\",\"sex\":\"grouping\",\"age\":\"not needed\"}}\n"
            ),
        )
        chain = reason_prompt | self.llm | StrOutputParser()
        response_text = chain.invoke({
            "query": query,
            "columns": ", ".join(columns),
        })

        # Clean up the response - remove markdown code blocks if present
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```"):
            # Remove markdown code fence
            lines = cleaned_text.split("\n")
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned_text = "\n".join(lines).strip()

        data = None
        try:
            data = json.loads(cleaned_text)
        except Exception:
            try:
                data = ast.literal_eval(cleaned_text)
            except Exception as e:
                raise ValueError(f"Model did not return valid JSON for reasoning. Got: {cleaned_text[:200]}") from e

        keep = data.get("keep", []) if isinstance(data, dict) else []
        prune_out = data.get("prune", []) if isinstance(data, dict) else []
        reasons = data.get("reasons", {}) if isinstance(data, dict) else {}

        # Validate against available columns (case-insensitive mapping)
        name_map = {c.lower(): c for c in columns}
        seen = set()
        pruned: List[str] = []
        for item in keep:
            if isinstance(item, str):
                key = item.strip().lower()
                if key in name_map and name_map[key] not in seen:
                    seen.add(name_map[key])
                    pruned.append(name_map[key])

        # Normalize reasons to actual column names
        norm_reasons: Dict[str, str] = {}
        if isinstance(reasons, dict):
            for k, v in reasons.items():
                if not isinstance(k, str):
                    continue
                key = k.strip().lower()
                if key in name_map:
                    norm_reasons[name_map[key]] = str(v)

        # Compute pruned-out list intersecting available columns
        norm_prune_out: List[str] = []
        for item in prune_out:
            if isinstance(item, str):
                key = item.strip().lower()
                if key in name_map:
                    norm_prune_out.append(name_map[key])

        if not pruned:
            raise ValueError("No valid columns selected. Ensure output uses exact available names.")

        return pruned, norm_reasons, norm_prune_out

    def prune_offline_simple(self, query: str, columns: List[str]) -> List[str]:
        """Heuristic, LLM-free pruning by keyword and synonym matching.
        - Uses synonyms (e.g. 'results' matches 'marks')
        - Uses fuzzy substring matching (e.g. 'sem' matches 'semester_id')
        - Returns all columns as a safety fallback if no specific matches found.
        """
        q = query.lower()
        # Tokenize query nicely
        q_tokens = set(re.findall(r"[a-z0-9]+", q))
        
        # Define domain synonyms to bridge query terms to DB column names
        synonyms = {
            # result/grade queries
            "result":     ["marks", "grade", "score", "performance", "gpa", "cgpa", "sgpa",
                           "percentage", "grand_total", "numeric_marks", "grade_text", "raw_result"],
            "marks":      ["result", "grade", "score", "numeric_marks", "grade_text", "raw_result"],
            "grade":      ["marks", "result", "score", "grade_text", "sgpa", "percentage"],
            "score":      ["marks", "grade", "sgpa", "percentage", "numeric_marks"],
            "gpa":        ["sgpa", "percentage", "grade", "marks"],
            "sgpa":       ["gpa", "percentage", "grade", "marks"],
            "percentage": ["sgpa", "gpa", "grand_total", "marks"],
            "average":    ["sgpa", "percentage", "grand_total", "numeric_marks"],
            # semester queries
            "sem":        ["semester", "term", "session", "academic", "semester_no", "session_id"],
            "semester":   ["sem", "session", "semester_no", "academic"],
            # student queries
            "student":    ["name", "roll", "id", "usn", "email", "student_usn", "student_name"],
            "name":       ["student", "usn", "student_name", "student_usn"],
            "usn":        ["student_usn", "student_name", "roll", "id"],
            # subject queries
            "subject":    ["course", "code", "title", "branch", "dept", "subject_code", "subject_label"],
            "course":     ["subject", "subject_code", "subject_label"],
            "info":       ["name", "detail", "profile", "description"],
        }

        # Expand query tokens with synonyms
        expanded_tokens = q_tokens.copy()
        for t in q_tokens:
            for root, syns in synonyms.items():
                if t == root or t in syns:
                    expanded_tokens.update(syns)
                    expanded_tokens.add(root)

        selected: List[str] = []
        for c in columns:
            cl = c.lower()
            # 1. Exact or Substring match (e.g. 'sem' in 'semester_id')
            if any(t in cl for t in q_tokens if len(t) >= 3):
                selected.append(c)
                continue
            
            # 2. Token overlap (e.g. 'marks' in ['subject', 'marks'])
            c_parts = set(re.findall(r"[a-z0-9]+", cl))
            if c_parts & expanded_tokens:
                selected.append(c)
        
        # Safety fallback: No mock data! 
        # If nothing matched the query, return all columns so the user can see their data.
        if not selected:
            return columns

        # Deduplicate preserving order
        seen = set(); dedup = []
        for c in selected:
            if c not in seen:
                seen.add(c); dedup.append(c)
        return dedup

    def prune(self, query: str, columns: List[str]) -> List[str]:
        self._init_llm()
        response_text = self.chain.invoke({
            "query": query,
            "columns": ", ".join(columns),
        })

        # Clean up the response - remove markdown code blocks if present
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```"):
            # Remove markdown code fence
            lines = cleaned_text.split("\n")
            # Remove first line (```python or ``` or ```json)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned_text = "\n".join(lines).strip()

        # Parse model output strictly
        try:
            parsed = ast.literal_eval(cleaned_text)
        except Exception as e:
            raise ValueError(f"Model did not return a valid Python list of strings. Got: {cleaned_text[:200]}") from e

        if not (isinstance(parsed, list) and all(isinstance(x, str) for x in parsed)):
            raise ValueError("Model did not return a valid Python list of strings.")

        # Build case-insensitive map to actual column names
        name_map = {c.lower(): c for c in columns}
        seen = set()
        pruned: List[str] = []
        for item in parsed:
            key = item.strip().lower()
            if key in name_map:
                actual = name_map[key]
                if actual not in seen:
                    seen.add(actual)
                    pruned.append(actual)

        if not pruned:
            raise ValueError("No valid columns selected. Ensure you choose only from the available columns.")

        return pruned


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Column Pruning Agent CLI")
    parser.add_argument("--query", type=str, help="Natural language query to answer")
    parser.add_argument("--columns", type=str, help="Comma-separated list of columns to prune")
    args = parser.parse_args()

    agent = ColumnPruningAgent()

    if args.query and args.columns:
        cols = [c.strip() for c in args.columns.split(",")]
        print(f"\n[Query]: {args.query}")
        print(f"[Available Columns]: {cols}")
        
        has_key = bool(os.getenv("GOOGLE_API_KEY"))
        if has_key:
            try:
                pruned, reasons, dropped = agent.prune_with_reason(args.query, cols)
                print("\n[Pruned Results (LLM)]")
                print(f"Keep: {pruned}")
                print(f"Drop: {dropped}")
            except Exception as e:
                print(f"LLM Pruning failed: {e}")
        else:
            pruned = agent.prune_offline_simple(args.query, cols)
            print("\n[Pruned Results (Heuristic)]")
            print(f"Keep: {pruned}")
            print(f"Note: Set GOOGLE_API_KEY for full LLM reasoning.")
    else:
        print("Usage: python column_agent.py --query 'my query' --columns 'col1,col2,col3'")
