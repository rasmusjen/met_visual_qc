from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import pandas as pd
import plotly.graph_objects as go
import plotly.subplots as sp

from .config import QCConfig
from .filenames import parse_raw_filename


def apply_var_min_max(df: pd.DataFrame, ts: str, limits: List[tuple], remove: bool = False):
    """Apply min/max screening.

    Args:
        df: input DataFrame (must contain ts column)
        ts: timestamp column name
        limits: list of tuples (pattern, min, max) where pattern ending with '_' is treated as prefix
        remove: if True, rows out of range are removed from returned DataFrame

    Returns:
        (filtered_df, out_of_range_report)
    """
    out_of_range_report = {}
    if not limits or df.empty:
        return df if remove else df.copy(), out_of_range_report

    for var in [c for c in df.columns if c != ts]:
        applicable = None
        for pattern, mn, mx in limits:
            if pattern.endswith("_"):
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
        intervals = []
        start = prev = idxs[0]
        for i in idxs[1:]:
            if i == prev + 1:
                prev = i
                continue
            intervals.append((start, prev))
            start = prev = i
        intervals.append((start, prev))
        display = []
        for a, b in intervals:
            t0 = pd.to_datetime(df.loc[a, ts])
            t1 = pd.to_datetime(df.loc[b, ts])
            if a == b:
                val = df.loc[a, var]
                display.append({"type": "single", "time": t0.isoformat(), "value": float(val) if pd.notna(val) else None, "index": int(a)})
            else:
                display.append({"type": "range", "start": t0.isoformat(), "end": t1.isoformat(), "start_idx": int(a), "end_idx": int(b)})
        out_of_range_report[var] = display

    if remove and out_of_range_report:
        mask_allowed = pd.Series(True, index=df.index)
        for var, items in out_of_range_report.items():
            for it in items:
                if it["type"] == "single":
                    idx = it.get("index")
                    if idx in mask_allowed.index:
                        mask_allowed.at[idx] = False
                else:
                    a = it.get("start_idx")
                    b = it.get("end_idx")
                    if a is None or b is None:
                        continue
                    mask_allowed.loc[a:b] = False
        return df.loc[mask_allowed].reset_index(drop=True), out_of_range_report

    return df.copy(), out_of_range_report


def build_qc_dashboard(cfg: QCConfig, df: pd.DataFrame, file_coverage: Optional[pd.DataFrame] = None) -> Path:
    """Build an interactive Plotly HTML QC dashboard.

    Returns path to saved HTML.
    """
    ts = cfg.timestamp.column
    vars_to_plot: List[str] = cfg.plot.variables_include or [c for c in df.columns if c != ts]

    # Optionally resample
    if cfg.plot.resample:
        df = df.set_index(ts).resample(cfg.plot.resample).mean(numeric_only=True).reset_index()

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

    # Apply screening + optional removal via helper so filtered data is used for plotting and resampling
    df_filtered, out_of_range_report = apply_var_min_max(df, ts, limits, remove=bool(cfg.plot.plot_filter))
    # Use filtered df both for plotting traces and for any further resampling/aggregation
    df_to_plot = df_filtered.copy()
    df = df_filtered

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
            if v in df_to_plot.columns:
                # For raw and 30-min, P_ variables are lines; daily remains bars for sums
                if _agg_kind(v) == "sum":
                    fig.add_trace(go.Scatter(x=df_to_plot[ts], y=df_to_plot[v], mode="lines", name=v, showlegend=False), row=current_row, col=1)
                else:
                    fig.add_trace(go.Scatter(x=df_to_plot[ts], y=df_to_plot[v], mode="lines", name=v, showlegend=False), row=current_row, col=1)
            current_row += 1
        # 30min block
        dfi = df.set_index(ts)
        for v in vars_to_plot:
            if v in df.columns:
                agg = _agg_kind(v)
                if agg == "sum":
                    # For P_ series, resample sum but show as line for 30-min
                    s30 = dfi[v].resample("30min").sum(min_count=1)
                    fig.add_trace(go.Scatter(x=s30.index, y=s30.values, mode="lines", name=f"{v}-30m", showlegend=False), row=current_row, col=1)
                else:
                    s30 = dfi[v].resample("30min").mean()
                    fig.add_trace(go.Scatter(x=s30.index, y=s30.values, mode="lines", name=f"{v}-30m", showlegend=False), row=current_row, col=1)
            current_row += 1
        # daily block
        for v in vars_to_plot:
            if v in df.columns:
                agg = _agg_kind(v)
                if agg == "sum":
                    # daily sums shown as bars for precipitation-like vars
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

    # df_to_plot and out_of_range_report were prepared earlier

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

    # If data span more than a month, build a monthly + whole-period summary table per variable
    monthly_html = ""
    try:
        if not df_to_plot.empty and vars_to_plot:
            tmin = pd.to_datetime(df_to_plot[ts]).min()
            tmax = pd.to_datetime(df_to_plot[ts]).max()
            if (tmax - tmin).days >= 31:
                d = df_to_plot.copy()
                d[ts] = pd.to_datetime(d[ts])
                d = d.set_index(ts)
                # period range for months
                period_index = pd.period_range(start=tmin, end=tmax, freq='M')
                month_labels = [p.strftime('%Y-%m') for p in period_index]
                rows = {}
                grp = d.groupby(d.index.to_period('M'))
                for v in vars_to_plot:
                    agg = _agg_kind(v)
                    if agg == 'sum':
                        s = grp[v].sum(min_count=1)
                        whole = d[v].sum(min_count=1)
                    else:
                        s = grp[v].mean()
                        whole = d[v].mean()
                    vals = [s.get(p, pd.NA) for p in period_index]
                    # convert Period/NaN to floats where possible
                    vals = [float(x) if pd.notna(x) else None for x in vals]
                    whole_val = float(whole) if pd.notna(whole) else None
                    rows[v] = vals + [whole_val]
                cols = month_labels + ['Whole']
                df_summary = pd.DataFrame.from_dict(rows, orient='index', columns=cols)
                # simple formatting
                monthly_html = '<h3>Monthly summary</h3>' + df_summary.to_html(float_format='%.3f', na_rep='')
    except Exception:
        monthly_html = ''

    if out_html_snippet or monthly_html:
        # inject before closing </body>
        inject = out_html_snippet + monthly_html
        if "</body>" in raw_html:
            raw_html = raw_html.replace("</body>", inject + "</body>")

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
