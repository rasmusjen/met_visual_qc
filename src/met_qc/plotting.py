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
    lf = cfg.filters.logger_file or "All loggers"
    if ts in df.columns and not df.empty:
        tmin = pd.to_datetime(df[ts]).min()
        tmax = pd.to_datetime(df[ts]).max()
        period = f"{tmin:%Y-%m-%d} → {tmax:%Y-%m-%d}"
    else:
        period = "(no data)"
    title_text = f"{site} — {lf}<br><span style='font-size:0.9em'>Period: {period}</span>"
    # Add a compact meta annotation (vars/rows)
    meta_text = f"Vars: {nvars} · Rows: {len(df):,}"
    fig.update_layout(showlegend=False, title_text=title_text, title_x=0.5, margin=dict(t=110))
    fig.add_annotation(text=meta_text, xref="paper", yref="paper", x=0, y=1.08, showarrow=False, align="left", font=dict(size=12))

    # Read variable-specific min/max limits from config/var_min_max.csv if present
    limits_path = Path("config") / "var_min_max.csv"
    limits = []
    if limits_path.exists():
        try:
            vdf = pd.read_csv(limits_path)
            # expect columns: Variable, Min, Max
            for _, r in vdf.iterrows():
                var = str(r.get("Variable") or "").strip()
                try:
                    mn = float(r.get("Min"))
                except Exception:
                    mn = None
                try:
                    mx = float(r.get("Max"))
                except Exception:
                    mx = None
                if var:
                    limits.append((var, mn, mx))
        except Exception:
            limits = []

    # Screen raw data for out-of-range values using the limits
    out_of_range_report: dict = {}
    if limits and not df.empty:
        # operate on the raw dataframe (not resampled)
        for var in [c for c in df.columns if c != ts]:
            # find applicable limit: first matching prefix or exact match
            applicable = None
            for pattern, mn, mx in limits:
                if pattern.endswith("_"):
                    # treat as prefix
                    if var.upper().startswith(pattern.upper()):
                        applicable = (mn, mx)
                        break
                else:
                    if var.upper() == pattern.upper():
                        applicable = (mn, mx)
                        break
            if not applicable:
                continue
            mn, mx = applicable
            if mn is None and mx is None:
                continue
            mask = pd.Series(False, index=df.index)
            if mn is not None:
                mask = mask | (df[var] < mn)
            if mx is not None:
                mask = mask | (df[var] > mx)
            mask = mask.fillna(False)
            idxs = list(df.index[mask])
            if not idxs:
                continue
            # group consecutive indices into intervals
            intervals = []
            start = prev = idxs[0]
            for i in idxs[1:]:
                if i == prev + 1:
                    prev = i
                    continue
                # close interval
                intervals.append((start, prev))
                start = prev = i
            intervals.append((start, prev))
            # convert intervals to timestamp strings and sample values
            display = []
            for a, b in intervals:
                t0 = pd.to_datetime(df.loc[a, ts])
                t1 = pd.to_datetime(df.loc[b, ts])
                if a == b:
                    val = df.loc[a, var]
                    display.append({"type": "single", "time": t0.isoformat(), "value": float(val) if pd.notna(val) else None})
                else:
                    display.append({"type": "range", "start": t0.isoformat(), "end": t1.isoformat()})
            out_of_range_report[var] = display

    # If plot_filter is enabled, remove out-of-range samples from the dataframe
    if cfg.plot.plot_filter and out_of_range_report:
        # build a mask of allowed rows
        mask_allowed = pd.Series(True, index=df.index)
        for var, items in out_of_range_report.items():
            # mark indices in the original dataframe as False (remove)
            for it in items:
                if it["type"] == "single":
                    # find index of timestamp
                    idx = df.index[df[ts].astype(str) == it["time"]]
                    for i in idx:
                        mask_allowed.at[i] = False
                else:
                    # range: remove rows between start and end inclusive
                    start = pd.to_datetime(it["start"]) 
                    end = pd.to_datetime(it["end"]) 
                    rng = (pd.to_datetime(df[ts]) >= start) & (pd.to_datetime(df[ts]) <= end)
                    mask_allowed[rng.values] = False
        # apply mask
        df = df.loc[mask_allowed].reset_index(drop=True)

    # Render HTML and append out-of-range report under the figure
    raw_html = fig.to_html(full_html=True, include_plotlyjs="cdn")
    out_html_snippet = ""
    if out_of_range_report:
        lines = ["<h3>Out-of-range values</h3>", "<ul>"]
        for var, items in out_of_range_report.items():
            lines.append(f"<li><strong>{var}</strong><ul>")
            for it in items:
                if it["type"] == "single":
                    lines.append(f"<li>{it['time']}: {it['value']}</li>")
                else:
                    lines.append(f"<li>{it['start']} → {it['end']}</li>")
            lines.append("</ul></li>")
        lines.append("</ul>")
        out_html_snippet = "\n".join(lines)

    if out_html_snippet:
        # inject before closing </body>
        if "</body>" in raw_html:
            raw_html = raw_html.replace("</body>", out_html_snippet + "</body>")

    Path(out).write_text(raw_html, encoding="utf-8")
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
        if cfg.filters.logger_file:
            lf = cfg.filters.logger_file.upper()
            if f"{rid.level}_{rid.file}".upper() != lf:
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
