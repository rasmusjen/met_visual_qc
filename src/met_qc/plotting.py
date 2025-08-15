from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import pandas as pd
import plotly.graph_objects as go
import plotly.subplots as sp

from .config import QCConfig
from .filenames import parse_raw_filename


def build_qc_dashboard(cfg: QCConfig, df: pd.DataFrame, file_coverage: Optional[pd.DataFrame] = None) -> Path:
    """Build an interactive Plotly HTML QC dashboard.

    Returns path to saved HTML.
    """
    ts = cfg.timestamp.column
    vars_to_plot: List[str] = cfg.plot.variables_include or [c for c in df.columns if c != ts]

    # Optionally resample
    if cfg.plot.resample:
        df = df.set_index(ts).resample(cfg.plot.resample).mean(numeric_only=True).reset_index()

    # Build figure grouped by layer: all raw, then all 30min, then all daily
    nvars = len(vars_to_plot)
    var_rows = nvars * 3 if nvars > 0 else 0
    rows = var_rows if var_rows > 0 else 1  # ensure at least one row exists
    if cfg.plot.include_missing_heatmap:
        rows += 1
    # compute file coverage if requested and not provided
    if cfg.plot.include_file_coverage and (file_coverage is None or file_coverage.empty):
        file_coverage = _compute_file_coverage(cfg)

    if cfg.plot.include_file_coverage and file_coverage is not None and not file_coverage.empty:
        rows += 1

    titles: List[str] = []
    if nvars > 0:
        # raw block titles
        titles.extend([f"{v} (raw)" for v in vars_to_plot])
        # 30min block titles
        titles.extend([f"{v} (30min {_agg_kind(v)})" for v in vars_to_plot])
        # daily block titles
        titles.extend([f"{v} (daily {_agg_kind(v)})" for v in vars_to_plot])
    else:
        titles = ["Time Series"]
    if cfg.plot.include_missing_heatmap:
        titles.append("Missing Data")
    if cfg.plot.include_file_coverage and file_coverage is not None and not file_coverage.empty:
        titles.append("File Coverage")
    fig = sp.make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.04, subplot_titles=titles)

    # Time series traces grouped by layer (no legend)
    current_row = 1
    if nvars > 0:
        # raw block
        for v in vars_to_plot:
            if v in df.columns:
                if _agg_kind(v) == "sum":
                    # Precipitation-like variable -> bar
                    fig.add_trace(go.Bar(x=df[ts], y=df[v], name=v, showlegend=False), row=current_row, col=1)
                else:
                    fig.add_trace(go.Scatter(x=df[ts], y=df[v], mode="lines", name=v, showlegend=False), row=current_row, col=1)
            current_row += 1
        # 30min block
        dfi = df.set_index(ts)
        for v in vars_to_plot:
            if v in df.columns:
                agg = _agg_kind(v)
                if agg == "sum":
                    s30 = dfi[v].resample("30min").sum(min_count=1)
                    fig.add_trace(go.Bar(x=s30.index, y=s30.values, name=f"{v}-30m", showlegend=False), row=current_row, col=1)
                else:
                    s30 = dfi[v].resample("30min").mean()
                    fig.add_trace(go.Scatter(x=s30.index, y=s30.values, mode="lines", name=f"{v}-30m", showlegend=False), row=current_row, col=1)
            current_row += 1
        # daily block
        for v in vars_to_plot:
            if v in df.columns:
                agg = _agg_kind(v)
                if agg == "sum":
                    sD = dfi[v].resample("1D").sum(min_count=1)
                    fig.add_trace(go.Bar(x=sD.index, y=sD.values, name=f"{v}-1d", showlegend=False), row=current_row, col=1)
                else:
                    sD = dfi[v].resample("1D").mean()
                    fig.add_trace(go.Scatter(x=sD.index, y=sD.values, mode="lines", name=f"{v}-1d", showlegend=False), row=current_row, col=1)
            current_row += 1

    # Next available row after the variable blocks
    row_idx = current_row if nvars > 0 else 2
    # Missing data heatmap
    if cfg.plot.include_missing_heatmap:
        miss = df.copy()
        if vars_to_plot:
            miss["missing"] = miss[vars_to_plot].isna().sum(axis=1)
        else:
            miss["missing"] = miss[ts].isna().astype(int)
        fig.add_trace(go.Heatmap(x=miss[ts], y=["missing"] * len(miss), z=miss["missing"], colorscale="Reds"), row=row_idx, col=1)
        row_idx += 1

    # File coverage chart (stacked per day, keyed by file id e.g., L05_F02)
    if cfg.plot.include_file_coverage and file_coverage is not None and not file_coverage.empty and row_idx <= rows:
        cov = file_coverage.copy()
        # Expect columns: date (date or datetime), key (str), value (int)
        if "key" not in cov.columns:
            # fallback if user provided simple rows/day format
            cov = cov.rename(columns={"rows": "value"})
            cov["key"] = "all"
        cov["date"] = pd.to_datetime(cov["date"]).dt.normalize()
        wide = cov.pivot_table(index="date", columns="key", values="value", aggfunc="sum", fill_value=0)
        wide = wide.sort_index()
        for k in wide.columns:
            fig.add_trace(go.Bar(x=wide.index, y=wide[k], name=str(k), showlegend=False), row=row_idx, col=1)
        fig.update_layout(barmode="stack", showlegend=False)

    out = Path(cfg.output_dir) / cfg.plot.output_html
    out.parent.mkdir(parents=True, exist_ok=True)
    # Build header/title info
    site = cfg.site_id
    lvl = cfg.filters.level_code or "All levels"
    fcode = cfg.filters.file_code or "All files"
    if ts in df.columns and not df.empty:
        tmin = pd.to_datetime(df[ts]).min()
        tmax = pd.to_datetime(df[ts]).max()
        period = f"{tmin:%Y-%m-%d} → {tmax:%Y-%m-%d}"
    else:
        period = "(no data)"
    title_text = f"{site} — {lvl} — {fcode}<br><span style='font-size:0.9em'>Period: {period}</span>"
    # Add a compact meta annotation (vars/rows)
    meta_text = f"Vars: {nvars} · Rows: {len(df):,}"
    fig.update_layout(showlegend=False, title_text=title_text, title_x=0.5, margin=dict(t=110))
    fig.add_annotation(text=meta_text, xref="paper", yref="paper", x=0, y=1.08, showarrow=False, align="left", font=dict(size=12))
    fig.write_html(str(out), include_plotlyjs="cdn", full_html=True)
    return out


def _compute_file_coverage(cfg: QCConfig) -> pd.DataFrame:
    """Compute per-day file coverage by scanning input_dir for matching .dat files.

    Returns a DataFrame with columns: date (datetime64[ns]), key (str), value (int=1)
    where key is the (level_file) identifier like "L05_F02".
    """
    base = Path(cfg.input_dir)
    rows: List[dict] = []
    for p in base.glob(cfg.file_glob):
        rid = parse_raw_filename(p.name)
        if not rid:
            continue
        if rid.site != cfg.site_id:
            continue
        if cfg.filters.level_code and rid.level != cfg.filters.level_code:
            continue
        if cfg.filters.file_code and rid.file != cfg.filters.file_code:
            continue
        key = f"{rid.level}_{rid.file}"
        rows.append({"date": pd.Timestamp(rid.date), "key": key, "value": 1})
    if not rows:
        return pd.DataFrame()
    cov = pd.DataFrame(rows)
    # ensure one row per (date, key) with value summed (in case of duplicates)
    cov = cov.groupby(["date", "key"], as_index=False)["value"].sum()
    return cov


def _agg_kind(var: str) -> str:
    """Return aggregation kind for variable name: 'sum' for P_* (precip), else 'mean'."""
    return "sum" if var.upper().startswith("P_") else "mean"
