import os
import sys
import time
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

import pandas as pd  # type: ignore
import numpy as np  # type: ignore
from dotenv import load_dotenv

# Load .env from the same directory as this file
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

import google.generativeai as genai  # type: ignore

from monday_client import get_board_items, get_boards, find_board_by_name, health_check
from data_processor import items_to_dataframe, clean_dataframe, data_quality_report
from leadership_report import generate_leadership_report


def _get_gemini_key() -> str:
    """Read Gemini key fresh from environment."""
    return os.getenv("GEMINI_API_KEY", "")


def _get_board_id(name: str) -> str:
    """Read board ID fresh from environment."""
    return os.getenv(name, "")


# Configure Gemini on import if key is available
_gemini_key = _get_gemini_key()
if _gemini_key:
    genai.configure(api_key=_gemini_key)


# --- Data Cache ---
class DataCache:
    """Simple TTL-based cache for board data."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any:
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            del self._cache[key]
        return None

    def set(self, key: str, data: Any) -> None:
        self._cache[key] = (data, time.time())

    def invalidate(self) -> None:
        self._cache.clear()


_cache = DataCache(ttl_seconds=300)


# --- BI Agent ---

class BIAgent:

    def __init__(self, work_orders_id: str = "", deals_id: str = ""):
        self.work_orders_id = work_orders_id or _get_board_id("WORK_ORDERS_BOARD_ID")
        self.deals_id = deals_id or _get_board_id("DEALS_BOARD_ID")
        self.conversation_history: list[dict[str, Any]] = []

        # Auto-discover board IDs if not provided
        if not self.work_orders_id or not self.deals_id:
            self._discover_boards()

        # Initialize Gemini model
        self.model = None
        gemini_key = _get_gemini_key()
        if gemini_key:
            genai.configure(api_key=gemini_key)
            self.model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=self._build_system_prompt(),
            )

    def _discover_boards(self) -> None:
        """Try to find board IDs by name."""
        try:
            if not self.work_orders_id:
                board = find_board_by_name("work order")
                if board:
                    self.work_orders_id = board["id"]

            if not self.deals_id:
                board = find_board_by_name("deal")
                if board:
                    self.deals_id = board["id"]
        except Exception:
            pass

    def _build_system_prompt(self) -> str:
        return """You are a Business Intelligence assistant for a company that uses Monday.com to manage Work Orders and Deals.

Your role:
- Answer founder-level business questions clearly and concisely
- Provide insights about revenue, pipeline health, sectoral performance, and operational metrics
- When data is incomplete or messy, acknowledge it and provide the best available answer
- Ask clarifying questions when a query is ambiguous
- Use tables, bullet points, and bold text for readability
- Include specific numbers and percentages when possible
- Always mention data caveats (e.g., "Note: 15% of deal values are missing")

You receive structured data summaries from the system. Use them to answer the user's question.
Do NOT make up numbers. Only use what is provided in the data context.
Format monetary values with ₹ symbol and commas.
When you don't have enough data to answer, say so clearly and suggest what data might help."""

    def load_data(self) -> tuple[Any, Any, list[str]]:
        """Load and clean data from both Monday.com boards with caching."""
        work_df = pd.DataFrame()
        deals_df = pd.DataFrame()
        errors: list[str] = []

        if self.work_orders_id:
            cached = _cache.get(f"work_{self.work_orders_id}")
            if cached is not None:
                work_df = cached
            else:
                try:
                    work_raw = get_board_items(self.work_orders_id)
                    work_df = items_to_dataframe(work_raw)
                    work_df = clean_dataframe(work_df)
                    _cache.set(f"work_{self.work_orders_id}", work_df)
                except Exception as e:
                    errors.append(f"Work Orders board error: {str(e)}")
        else:
            errors.append("Work Orders board ID not configured")

        if self.deals_id:
            cached = _cache.get(f"deals_{self.deals_id}")
            if cached is not None:
                deals_df = cached
            else:
                try:
                    deals_raw = get_board_items(self.deals_id)
                    deals_df = items_to_dataframe(deals_raw)
                    deals_df = clean_dataframe(deals_df)
                    _cache.set(f"deals_{self.deals_id}", deals_df)
                except Exception as e:
                    errors.append(f"Deals board error: {str(e)}")
        else:
            errors.append("Deals board ID not configured")

        return work_df, deals_df, errors

    def _build_data_context(self, work_df: Any, deals_df: Any) -> str:
        """Build a rich data context string for the LLM."""
        context_parts: list[str] = []

        # Deals context
        if not deals_df.empty:
            context_parts.append("=== DEALS DATA ===")
            context_parts.append(f"Total deals: {len(deals_df)}")
            context_parts.append(f"Columns: {', '.join(deals_df.columns.tolist())}")

            # Summary statistics for numeric columns
            numeric_cols = deals_df.select_dtypes(include=[np.number]).columns.tolist()
            for col in numeric_cols:
                non_null = deals_df[col].dropna()
                if len(non_null) > 0:
                    context_parts.append(
                        f"\n{col}: sum={non_null.sum():,.0f}, avg={non_null.mean():,.0f}, "
                        f"min={non_null.min():,.0f}, max={non_null.max():,.0f}, "
                        f"non-null count={len(non_null)}/{len(deals_df)}"
                    )

            # Categorical breakdowns
            cat_cols = deals_df.select_dtypes(include=["object"]).columns.tolist()
            for col in cat_cols:
                unique_count = deals_df[col].nunique()
                if 1 < unique_count <= 20:
                    value_counts = deals_df[col].value_counts().head(15)
                    context_parts.append(f"\n{col} breakdown:")
                    for val, count in value_counts.items():
                        if val is not None and str(val).strip():
                            context_parts.append(f"  - {val}: {count}")

            # Cross-tabulations for key dimensions
            sector_col = _find_col(deals_df, ["sector", "industry", "vertical", "segment"])
            value_col = _find_col(deals_df, ["value", "amount", "revenue", "deal size", "price"])
            stage_col = _find_col(deals_df, ["stage", "status", "phase", "deal stage"])

            if sector_col and value_col:
                deals_df[value_col] = pd.to_numeric(deals_df[value_col], errors="coerce")
                sector_rev = deals_df.groupby(sector_col)[value_col].agg(["sum", "count", "mean"])
                context_parts.append(f"\nRevenue by {sector_col}:")
                for idx, row in sector_rev.iterrows():
                    if idx is not None and str(idx).strip():
                        context_parts.append(
                            f"  - {idx}: total=₹{row['sum']:,.0f}, "
                            f"deals={int(row['count'])}, avg=₹{row['mean']:,.0f}"
                        )

            if stage_col and value_col:
                stage_rev = deals_df.groupby(stage_col)[value_col].agg(["sum", "count"])
                context_parts.append(f"\nPipeline by {stage_col}:")
                for idx, row in stage_rev.iterrows():
                    if idx is not None and str(idx).strip():
                        context_parts.append(
                            f"  - {idx}: value=₹{row['sum']:,.0f}, count={int(row['count'])}"
                        )

            # Data quality
            context_parts.append(f"\n{data_quality_report(deals_df, 'Deals')}")

        else:
            context_parts.append("=== DEALS DATA ===\nNo deals data available.")

        # Work Orders context
        if not work_df.empty:
            context_parts.append("\n=== WORK ORDERS DATA ===")
            context_parts.append(f"Total work orders: {len(work_df)}")
            context_parts.append(f"Columns: {', '.join(work_df.columns.tolist())}")

            # Numeric summaries
            numeric_cols = work_df.select_dtypes(include=[np.number]).columns.tolist()
            for col in numeric_cols:
                non_null = work_df[col].dropna()
                if len(non_null) > 0:
                    context_parts.append(
                        f"\n{col}: sum={non_null.sum():,.0f}, avg={non_null.mean():,.0f}, "
                        f"min={non_null.min():,.0f}, max={non_null.max():,.0f}, "
                        f"non-null count={len(non_null)}/{len(work_df)}"
                    )

            # Categorical breakdowns
            cat_cols = work_df.select_dtypes(include=["object"]).columns.tolist()
            for col in cat_cols:
                unique_count = work_df[col].nunique()
                if 1 < unique_count <= 20:
                    value_counts = work_df[col].value_counts().head(15)
                    context_parts.append(f"\n{col} breakdown:")
                    for val, count in value_counts.items():
                        if val is not None and str(val).strip():
                            context_parts.append(f"  - {val}: {count}")

            context_parts.append(f"\n{data_quality_report(work_df, 'Work Orders')}")
        else:
            context_parts.append("\n=== WORK ORDERS DATA ===\nNo work orders data available.")

        # Raw sample data (first few rows)
        if not deals_df.empty:
            context_parts.append("\n=== DEALS SAMPLE (first 5 rows) ===")
            context_parts.append(deals_df.head(5).to_string(index=False))

        if not work_df.empty:
            context_parts.append("\n=== WORK ORDERS SAMPLE (first 5 rows) ===")
            context_parts.append(work_df.head(5).to_string(index=False))

        return "\n".join(context_parts)

    def chat(self, user_message: str) -> str:
        """Process a user message and return an AI-generated response."""
        if self.model is None:
            return "⚠️ Gemini API key not configured. Please set GEMINI_API_KEY environment variable."

        # Load data from Monday.com
        try:
            work_df, deals_df, load_errors = self.load_data()
        except Exception as e:
            return (
                f"❌ Failed to load data from Monday.com: {str(e)}\n\n"
                "Please check your API key and board IDs."
            )

        # Build context
        data_context = self._build_data_context(work_df, deals_df)

        # Add load errors as caveats
        caveats = ""
        if load_errors:
            caveats = "\n⚠️ Data loading issues:\n" + "\n".join(
                f"- {e}" for e in load_errors
            )

        # Build the prompt
        augmented_message = (
            f"User Question: {user_message}\n\n"
            f"--- DATA CONTEXT ---\n"
            f"{data_context}\n"
            f"{caveats}\n"
            f"--- END DATA CONTEXT ---\n\n"
            f"Answer the user's question based on the data above. "
            f"Be specific, use numbers, and mention any data quality caveats."
        )

        # Maintain conversation history
        self.conversation_history.append(
            {"role": "user", "parts": [augmented_message]}
        )

        try:
            chat = self.model.start_chat(
                history=self.conversation_history[:-1]
            )
            response = chat.send_message(augmented_message)

            assistant_msg = response.text
            self.conversation_history.append(
                {"role": "model", "parts": [assistant_msg]}
            )

            # Keep history manageable (last 20 exchanges)
            if len(self.conversation_history) > 40:
                self.conversation_history = self.conversation_history[-20:]

            return assistant_msg

        except Exception as e:
            error_msg = str(e)
            if "quota" in error_msg.lower() or "rate" in error_msg.lower():
                return "⚠️ API rate limit reached. Please wait a moment and try again."
            return f"❌ Error generating response: {error_msg}"

    def get_leadership_report(self) -> str:
        """Generate a leadership update report."""
        try:
            work_df, deals_df, errors = self.load_data()
            report = generate_leadership_report(work_df, deals_df)
            if errors:
                report += "\n\n> ⚠️ " + " | ".join(errors)
            return report
        except Exception as e:
            return f"❌ Failed to generate report: {str(e)}"

    def refresh_data(self) -> str:
        """Force refresh cached data."""
        _cache.invalidate()
        return "✅ Data cache cleared. Next query will fetch fresh data from Monday.com."


def _find_col(df: Any, keywords: list[str]) -> Optional[str]:
    """Helper to find a column by keyword match."""
    for col in df.columns:
        col_lower = str(col).lower()
        for kw in keywords:
            if kw in col_lower:
                return str(col)
    return None
