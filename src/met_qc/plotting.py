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


def build_qc_dashboards(cfg: QCConfig, df: pd.DataFrame) -> List[Path]:
    """Build interactive Plotly HTML QC dashboards for raw, 30min, and daily data.

    Returns list of paths to saved HTML files.
    """
    ts = cfg.timestamp.column
    vars_to_plot: List[str] = cfg.plot.variables_include or [c for c in df.columns if c != ts]

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
    df = df_filtered

    # Compute file coverage if requested
    file_coverage = None
    if cfg.plot.include_file_coverage:
        file_coverage = _compute_file_coverage(cfg)

    paths = []

    # Raw data dashboard
    if cfg.plot.output_files.get("qc_raw.html", True):
        paths.append(_build_single_dashboard(cfg, df, vars_to_plot, "raw", file_coverage, out_of_range_report))

    # 30min aggregated dashboard
    if cfg.plot.output_files.get("qc_30min.html", True):
        df_30min = _resample_df(df, ts, "30min", vars_to_plot)
        paths.append(_build_single_dashboard(cfg, df_30min, vars_to_plot, "30min", file_coverage, out_of_range_report))

    # Daily aggregated dashboard
    if cfg.plot.output_files.get("qc_daily.html", True):
        df_daily = _resample_df(df, ts, "1D", vars_to_plot)
        paths.append(_build_single_dashboard(cfg, df_daily, vars_to_plot, "daily", file_coverage, out_of_range_report))

    return paths


def _resample_df(df: pd.DataFrame, ts: str, freq: str, vars_to_plot: List[str]) -> pd.DataFrame:
    """Resample dataframe to given frequency for the specified variables."""
    dfi = df.set_index(ts)
    resampled = {}
    for v in vars_to_plot:
        if v in df.columns:
            agg = _agg_kind(v)
            if agg == "sum":
                resampled[v] = dfi[v].resample(freq).sum(min_count=1)
            else:
                resampled[v] = dfi[v].resample(freq).mean()
    rdf = pd.DataFrame(resampled)
    rdf[ts] = rdf.index
    rdf = rdf.reset_index(drop=True)
    return rdf


def _build_single_dashboard(cfg: QCConfig, df: pd.DataFrame, vars_to_plot: List[str], level: str, file_coverage: Optional[pd.DataFrame], out_of_range_report: dict) -> Path:
    """Build a single dashboard for the given level (raw, 30min, daily)."""
    ts = cfg.timestamp.column
    nvars = len(vars_to_plot)
    rows = nvars
    titles = [f"{v} ({level})" for v in vars_to_plot]
    if cfg.plot.include_missing_heatmap:
        rows += 1
        titles.append("Missing Data")
    if cfg.plot.include_file_coverage and file_coverage is not None and not file_coverage.empty:
        rows += 1
        titles.append("File Coverage")

    vertical_spacing = 0.005  # small spacing for scrollable layout
    fig = sp.make_subplots(
        rows=rows, 
        cols=1, 
        shared_xaxes=True, 
        vertical_spacing=vertical_spacing, 
        subplot_titles=titles,
        row_heights=[1] * rows  # equal heights
    )

    current_row = 1
    for v in vars_to_plot:
        if v in df.columns:
            if _agg_kind(v) == "sum" and level == "daily":
                fig.add_trace(go.Bar(x=df[ts], y=df[v], name=v, showlegend=False), row=current_row, col=1)
            else:
                fig.add_trace(go.Scatter(x=df[ts], y=df[v], mode="lines", name=v, showlegend=False), row=current_row, col=1)
        current_row += 1

    if cfg.plot.include_missing_heatmap:
        missing_data = df[vars_to_plot].isnull().astype(int)
        fig.add_trace(go.Heatmap(
            z=missing_data.T.values,
            x=df[ts],
            y=vars_to_plot,
            colorscale="Greys",
            showscale=False,
            hoverongaps=False
        ), row=current_row, col=1)
        current_row += 1

    if cfg.plot.include_file_coverage and file_coverage is not None and not file_coverage.empty:
        file_coverage_pivot = file_coverage.pivot(index="date", columns="key", values="value").fillna(0)
        for col in file_coverage_pivot.columns:
            fig.add_trace(go.Bar(
                x=file_coverage_pivot.index,
                y=file_coverage_pivot[col],
                name=col,
                showlegend=False
            ), row=current_row, col=1)
        fig.update_layout(barmode="stack")

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
    fixed_subplot_height = 300  # pixels per subplot
    total_height = rows * fixed_subplot_height + 150  # extra for title and margins
    fig.update_layout(
        showlegend=False, 
        title_text=title_text, 
        title_x=0.5, 
        margin=dict(t=110),
        height=total_height
    )
    fig.add_annotation(text=meta_text, xref="paper", yref="paper", x=0, y=1.08, showarrow=False, align="left", font=dict(size=12))

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
        if not df.empty and vars_to_plot:
            tmin = pd.to_datetime(df[ts]).min()
            tmax = pd.to_datetime(df[ts]).max()
            if (tmax - tmin).days >= 31:
                d = df.copy()
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

    output_path = Path(cfg.output_dir) / f"qc_{level}.html"
    Path(output_path).write_text(raw_html, encoding="utf-8")
    return output_path


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
