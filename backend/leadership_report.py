import pandas as pd  # type: ignore
import numpy as np  # type: ignore
from typing import Any, Optional
from datetime import datetime


def generate_leadership_report(work_df: Any, deals_df: Any) -> str:
    """
    Generate a structured leadership update report in markdown format.

    Interpretation: A concise executive summary covering pipeline health,
    revenue highlights, operational status, and actionable insights —
    ready for founder/C-suite consumption.
    """
    now = datetime.now().strftime("%B %d, %Y")
    sections: list[str] = [f"# 📊 Leadership Update — {now}\n"]

    # ---- Pipeline Overview ----
    sections.append("## Pipeline Overview\n")
    if not deals_df.empty:
        total_deals = len(deals_df)
        sections.append(f"- **Total Deals**: {total_deals}")

        # Find deal value column
        value_col = _find_column(deals_df, ["value", "amount", "revenue", "deal size", "price"])
        if value_col:
            deals_df[value_col] = pd.to_numeric(deals_df[value_col], errors="coerce")
            total_value = deals_df[value_col].sum()
            avg_value = deals_df[value_col].mean()
            if total_value is not None and not np.isnan(float(total_value)):
                sections.append(f"- **Total Pipeline Value**: ₹{total_value:,.0f}")
                sections.append(f"- **Average Deal Size**: ₹{avg_value:,.0f}")

        # Stage distribution
        stage_col = _find_column(deals_df, ["stage", "status", "phase", "deal stage"])
        if stage_col:
            stage_counts = deals_df[stage_col].value_counts()
            sections.append("\n### Deal Stage Distribution\n")
            sections.append("| Stage | Count | % |")
            sections.append("|-------|------:|--:|")
            for stage, count in stage_counts.items():
                if stage is not None and str(stage).strip():
                    pct = count / total_deals * 100
                    sections.append(f"| {stage} | {count} | {pct:.0f}% |")

        # Sector breakdown
        sector_col = _find_column(deals_df, ["sector", "industry", "vertical", "segment", "domain"])
        if sector_col:
            sector_counts = deals_df[sector_col].value_counts()
            sections.append("\n### Sector Breakdown\n")
            sections.append("| Sector | Deals |")
            sections.append("|--------|------:|")
            for sector, count in sector_counts.items():
                if sector is not None and str(sector).strip():
                    sections.append(f"| {sector} | {count} |")

            # Sector-wise revenue
            if value_col:
                sections.append("\n### Revenue by Sector\n")
                sector_revenue = deals_df.groupby(sector_col)[value_col].sum().sort_values(ascending=False)
                sections.append("| Sector | Revenue |")
                sections.append("|--------|--------:|")
                for sector, rev in sector_revenue.items():
                    if sector is not None and str(sector).strip():
                        try:
                            if not np.isnan(float(rev)):
                                sections.append(f"| {sector} | ₹{rev:,.0f} |")
                        except (ValueError, TypeError):
                            pass
    else:
        sections.append("_No deals data available._\n")

    # ---- Operational Summary ----
    sections.append("\n## Operational Summary\n")
    if not work_df.empty:
        total_projects = len(work_df)
        sections.append(f"- **Total Work Orders**: {total_projects}")

        status_col = _find_column(work_df, ["status", "state", "progress", "stage"])
        if status_col:
            status_counts = work_df[status_col].value_counts()
            sections.append("\n### Project Status\n")
            sections.append("| Status | Count |")
            sections.append("|--------|------:|")
            for status, count in status_counts.items():
                if status is not None and str(status).strip():
                    sections.append(f"| {status} | {count} |")

        # Client distribution
        client_col = _find_column(work_df, ["client", "customer", "account", "company"])
        if client_col:
            top_clients = work_df[client_col].value_counts().head(10)
            sections.append("\n### Top Clients (by Work Orders)\n")
            sections.append("| Client | Projects |")
            sections.append("|--------|--------:|")
            for client, count in top_clients.items():
                if client is not None and str(client).strip():
                    sections.append(f"| {client} | {count} |")
    else:
        sections.append("_No work orders data available._\n")

    # ---- Data Quality Flags ----
    sections.append("\n## Data Quality Notes\n")
    quality_issues: list[str] = []
    for label, df in [("Deals", deals_df), ("Work Orders", work_df)]:
        if df.empty:
            quality_issues.append(f"- ⚠️ {label}: No data loaded")
            continue
        total_cells = int(df.size)
        missing = int(df.isna().sum().sum())
        pct = missing / total_cells * 100 if total_cells else 0
        if pct > 10:
            quality_issues.append(
                f"- ⚠️ {label}: {pct:.0f}% of fields are missing or empty"
            )

    if quality_issues:
        sections.extend(quality_issues)
    else:
        sections.append("- ✅ Data quality looks good across both boards.")

    # ---- Key Takeaways ----
    sections.append("\n## Key Takeaways\n")
    takeaways = _generate_takeaways(work_df, deals_df)
    for t in takeaways:
        sections.append(f"- {t}")

    sections.append("\n---\n_Report auto-generated by Monday.com BI Agent_")

    return "\n".join(sections)


def _find_column(df: Any, keywords: list[str]) -> Optional[str]:
    """Find the first column whose name matches any keyword."""
    for col in df.columns:
        col_lower = str(col).lower()
        for kw in keywords:
            if kw in col_lower:
                return str(col)
    return None


def _generate_takeaways(work_df: Any, deals_df: Any) -> list[str]:
    """Generate simple actionable takeaways from the data."""
    takeaways: list[str] = []

    if not deals_df.empty:
        value_col = _find_column(deals_df, ["value", "amount", "revenue", "deal size"])
        stage_col = _find_column(deals_df, ["stage", "status", "phase"])

        if value_col and stage_col:
            deals_df[value_col] = pd.to_numeric(deals_df[value_col], errors="coerce")
            by_stage = deals_df.groupby(stage_col)[value_col].sum().sort_values(ascending=False)
            if len(by_stage) > 0:
                top_stage = by_stage.index[0]
                top_val = by_stage.iloc[0]
                try:
                    if not np.isnan(float(top_val)):
                        takeaways.append(
                            f"Highest pipeline value is in **{top_stage}** stage (₹{top_val:,.0f})"
                        )
                except (ValueError, TypeError):
                    pass

        sector_col = _find_column(deals_df, ["sector", "industry", "vertical"])
        if sector_col:
            top_sector = deals_df[sector_col].value_counts()
            if len(top_sector) > 0:
                takeaways.append(
                    f"**{top_sector.index[0]}** leads in deal count ({top_sector.iloc[0]} deals)"
                )

    if not work_df.empty:
        status_col = _find_column(work_df, ["status", "state", "progress"])
        if status_col:
            status_counts = work_df[status_col].value_counts()
            active = sum(
                count
                for status, count in status_counts.items()
                if status is not None
                and any(
                    kw in str(status).lower()
                    for kw in ["active", "progress", "ongoing", "working"]
                )
            )
            if active > 0:
                takeaways.append(
                    f"{active} work orders currently in active/in-progress state"
                )

    if not takeaways:
        takeaways.append(
            "Insufficient structured data to generate automated takeaways"
        )

    return takeaways
