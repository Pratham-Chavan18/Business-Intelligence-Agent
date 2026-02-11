import re
import pandas as pd  # type: ignore
import numpy as np  # type: ignore
from typing import Any, Optional


# --- Sector / Industry Normalization ---
SECTOR_MAP: dict[str, str] = {
    "energy": "Energy",
    "oil": "Energy",
    "oil & gas": "Energy",
    "oil and gas": "Energy",
    "power": "Energy",
    "solar": "Energy",
    "wind energy": "Energy",
    "renewable": "Energy",
    "renewables": "Energy",
    "mining": "Mining",
    "mines": "Mining",
    "infrastructure": "Infrastructure",
    "infra": "Infrastructure",
    "construction": "Infrastructure",
    "real estate": "Real Estate",
    "realty": "Real Estate",
    "agriculture": "Agriculture",
    "agri": "Agriculture",
    "telecom": "Telecom",
    "telecommunications": "Telecom",
    "government": "Government",
    "govt": "Government",
    "defence": "Defence",
    "defense": "Defence",
    "survey": "Survey",
    "surveying": "Survey",
    "mapping": "Survey",
    "logistics": "Logistics",
    "transport": "Logistics",
    "transportation": "Logistics",
}


def items_to_dataframe(board_data: dict) -> Any:
    """
    Convert Monday.com board JSON into a pandas DataFrame.
    Uses column metadata to create human-readable column names.
    """
    try:
        board = board_data["data"]["boards"][0]
        items = board["items_page"]["items"]
        columns_meta = board.get("columns", [])
    except (KeyError, IndexError, TypeError):
        return pd.DataFrame()

    if not items:
        return pd.DataFrame()

    # Build column ID -> title mapping
    col_map: dict[str, str] = {}
    if columns_meta:
        col_map = {c["id"]: c["title"] for c in columns_meta}

    rows: list[dict[str, Any]] = []
    for item in items:
        row: dict[str, Any] = {"Item Name": item["name"]}

        # Add group info if available
        group = item.get("group")
        if group:
            row["Group"] = group.get("title", "")

        for col in item.get("column_values", []):
            col_name = col_map.get(col["id"], col["id"])
            text_val = col.get("text", "")
            row[col_name] = text_val if text_val else None

        rows.append(row)

    return pd.DataFrame(rows)


def clean_dates(df: Any) -> Any:
    """Parse date columns into datetime, handling multiple formats."""
    date_keywords = ["date", "created", "updated", "deadline", "due", "start", "end", "close"]
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in date_keywords):
            if df[col].dtype == "object":
                df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    return df


def parse_currency(value: Any) -> float:
    """Parse currency strings like '₹1,50,000' or '$15,000.50' into float."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return float("nan")
    # Remove currency symbols and commas
    s = re.sub(r"[₹$€£¥,\s]", "", s)
    # Handle Indian lakhs/crores written as text
    s = s.lower().replace("lakh", "00000").replace("cr", "0000000")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def clean_numbers(df: Any) -> Any:
    """Attempt to convert numeric-looking columns to numeric types."""
    money_keywords = ["value", "amount", "revenue", "price", "cost", "budget", "deal"]
    for col in df.columns:
        if df[col].dtype != "object":
            continue
        col_lower = str(col).lower()

        # Check if it's a money column
        if any(kw in col_lower for kw in money_keywords):
            df[col] = df[col].apply(parse_currency)
            continue

        # Try general numeric conversion
        sample = df[col].dropna().head(20)
        if len(sample) == 0:
            continue
        numeric_count = 0
        for v in sample:
            try:
                float(str(v).replace(",", ""))
                numeric_count += 1
            except (ValueError, TypeError):
                pass
        if numeric_count > len(sample) * 0.6:
            df[col] = df[col].apply(
                lambda x: float(str(x).replace(",", ""))
                if x is not None and str(x).strip() else float("nan")
            )
    return df


def normalize_text(df: Any) -> Any:
    """Strip whitespace and normalize text fields."""
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].apply(
                lambda x: x.strip() if isinstance(x, str) else x
            )
    return df


def normalize_sectors(df: Any) -> Any:
    """Normalize sector/industry column values."""
    sector_keywords = ["sector", "industry", "vertical", "segment", "domain"]
    for col in df.columns:
        if any(kw in str(col).lower() for kw in sector_keywords):
            if df[col].dtype == "object":
                df[col] = df[col].apply(
                    lambda x: SECTOR_MAP.get(
                        str(x).strip().lower(), str(x).strip().title()
                    )
                    if x is not None and str(x).strip() else x
                )
    return df


def clean_dataframe(df: Any) -> Any:
    """Apply all cleaning transformations."""
    if df.empty:
        return df
    df = normalize_text(df)
    df = clean_dates(df)
    df = clean_numbers(df)
    df = normalize_sectors(df)
    return df


def data_quality_report(df: Any, board_name: str = "Board") -> str:
    """Generate a data quality summary for a dataframe."""
    if df.empty:
        return f"**{board_name}**: No data available."

    total_rows = len(df)
    total_cells = int(df.size)
    missing_cells = int(df.isna().sum().sum())
    missing_pct = (missing_cells / total_cells * 100) if total_cells > 0 else 0

    lines = [
        f"**{board_name}** — {total_rows} records",
        f"- Data completeness: {100 - missing_pct:.1f}%",
    ]

    # Columns with high missing rates
    for col in df.columns:
        col_missing = int(df[col].isna().sum())
        if col_missing > 0:
            pct = col_missing / total_rows * 100
            if pct > 30:
                lines.append(f"- ⚠️ `{col}`: {pct:.0f}% missing")

    return "\n".join(lines)
