from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Iterable
from datetime import datetime, date
import logging
import pandas as pd

from .config import QCConfig
from .filenames import parse_raw_filename
from .headers import HeaderTimeline, HeaderColumn

logger = logging.getLogger(__name__)


def _select_header_for_raw(tl: HeaderTimeline, raw_name: str) -> Optional[List[HeaderColumn]]:
    rid = parse_raw_filename(raw_name)
    if not rid:
        return None
    dt0 = datetime.combine(rid.date, datetime.min.time())
    return tl.resolve(rid.site, rid.level, rid.file, dt0)


def _apply_mapping(df: pd.DataFrame, mapping: List[HeaderColumn]) -> pd.DataFrame:
    # The raw file is expected to have columns in the same order; assign names
    names = ["TIMESTAMP"] + [c.name for c in mapping[1:]] if mapping and mapping[0].name.upper() == "TIMESTAMP" else [c.name for c in mapping]
    df = df.copy()
    if len(names) != df.shape[1]:
        raise ValueError(f"Header-column count mismatch: header={len(names)} data={df.shape[1]}")
    df.columns = names
    # scale/offset
    for c in mapping:
        if c.name == "TIMESTAMP":
            continue
        if c.name in df.columns:
            df[c.name] = df[c.name].astype(float, errors="ignore")
            df[c.name] = df[c.name] * c.scale_factor + c.offset
    return df


def ingest_and_merge(cfg: QCConfig, timeline: HeaderTimeline, date_from: Optional[date] = None, date_to: Optional[date] = None) -> pd.DataFrame:
    base = Path(cfg.input_dir)
    # Only consider files that match the raw filename pattern
    files = sorted([p for p in base.glob(cfg.file_glob) if parse_raw_filename(p.name)])
    if cfg.filters.logger_file:
        def keep(p: Path) -> bool:
            rid = parse_raw_filename(p.name)
            if not rid:
                return False
            site_key = ''.join(c for c in cfg.site_id.upper() if c.isalnum())
            if rid.site != site_key:
                return False
            lf = cfg.filters.logger_file.upper()
            if f"{rid.level}_{rid.file}".upper() != lf:
                return False
            return True
        files = [p for p in files if keep(p)]
    # Apply date-range filter on filenames if provided
    if date_from or date_to:
        def in_range(p: Path) -> bool:
            rid = parse_raw_filename(p.name)
            if not rid:
                return False
            if date_from and rid.date < date_from:
                return False
            if date_to and rid.date > date_to:
                return False
            return True
        files = [p for p in files if in_range(p)]

    out_frames: List[pd.DataFrame] = []
    na_vals = cfg.ingest.nan_values
    for p in files:
        mapping = _select_header_for_raw(timeline, p.name)
        if not mapping:
            logger.warning(f"No header for file {p.name}; skipping")
            continue
        try:
            df = pd.read_csv(p, header=None, names=None if cfg.ingest.has_header_row else None, na_values=na_vals)
        except pd.errors.ParserError as e:
            logger.warning(f"Failed to parse file {p.name}: {e}; skipping")
            continue
        try:
            df = _apply_mapping(df, mapping)
        except Exception as e:
            logger.warning(f"Skipping {p.name} due to mapping error: {e}")
            continue
        # Parse timestamp
        ts_col = cfg.timestamp.column
        df[ts_col] = pd.to_datetime(df[ts_col].astype(str), format=cfg.timestamp.raw_format, errors="coerce")
        # Coerce numeric
        if cfg.ingest.coerce_numeric:
            for col in df.columns:
                if col == ts_col:
                    continue
                df[col] = pd.to_numeric(df[col], errors="coerce")
        out_frames.append(df)
    if not out_frames:
        return pd.DataFrame()
    merged = pd.concat(out_frames, ignore_index=True)
    # Sort/drop dupes
    if cfg.merge.sort_by_timestamp:
        merged = merged.sort_values(cfg.timestamp.column)
    if cfg.merge.drop_duplicates:
        merged = merged.drop_duplicates(subset=[cfg.timestamp.column], keep="first")
    
    # Load variable min/max limits from config/var_min_max.csv for filtering CSV outputs
    limits = []
    limits_path = Path("config") / "var_min_max.csv"
    if limits_path.exists():
        try:
            lim_df = pd.read_csv(limits_path)
            for _, row in lim_df.iterrows():
                var = row.get("Variable")
                mn = row.get("Min")
                mx = row.get("Max")
                mn = None if pd.isna(mn) else float(mn)
                mx = None if pd.isna(mx) else float(mx)
                if var:
                    limits.append((var, mn, mx))
        except Exception as e:
            logger.warning(f"Failed to load var_min_max.csv: {e}")
            limits = []
    
    # Helper function to apply filtering to a copy of the dataframe
    def apply_filtering(df):
        """Apply out-of-range filtering to a copy of the dataframe"""
        df_filtered = df.copy()
        data_cols = [col for col in df_filtered.columns if col != cfg.timestamp.column]
        skip_prefixes = ("G_SF_", "G_ISCAL_", "G_IU_", "D_SNOW_IU_")
        if limits:
            for var in data_cols:
                if var.startswith(skip_prefixes):
                    continue
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
                if applicable:
                    mn, mx = applicable
                    series = pd.to_numeric(df_filtered[var], errors="coerce")
                    if mn is not None:
                        df_filtered.loc[series < mn, var] = pd.NA
                    if mx is not None:
                        df_filtered.loc[series > mx, var] = pd.NA
        return df_filtered
    
    # Write outputs
    cfg.output_path().mkdir(parents=True, exist_ok=True)
    # Save unfiltered data to parquet for archival
    merged.to_parquet(str(cfg.output_path() / cfg.merge.output_parquet), index=False)
    if cfg.merge.output_csv:
        # Apply filtering, replace NaN with -9999, and format timestamp
        merged_output = apply_filtering(merged)
        merged_output = merged_output.fillna(-9999)
        if cfg.timestamp.column in merged_output.columns:
            merged_output[cfg.timestamp.column] = pd.to_datetime(merged_output[cfg.timestamp.column]).dt.strftime('%Y%m%d%H%M')
        merged_output.to_csv(str(cfg.output_path() / cfg.merge.output_csv), index=False)
    if cfg.merge.output_30min_csv:
        logger.info(f"Creating 30min CSV: {cfg.merge.output_30min_csv}")
        try:
            # Apply filtering first, then resample to 30min intervals
            merged_filtered = apply_filtering(merged)
            merged_30min = merged_filtered.set_index(cfg.timestamp.column).resample('30min', closed='left', label='left').mean().reset_index()
            
            # Create TIMESTAMP_START and TIMESTAMP_END columns
            # TIMESTAMP_START is the beginning of the 30min period
            # TIMESTAMP_END is the beginning of the next 30min period (00 or 30 minutes)
            merged_30min['TIMESTAMP_START'] = pd.to_datetime(merged_30min[cfg.timestamp.column]).dt.strftime('%Y%m%d%H%M')
            end_times = pd.to_datetime(merged_30min[cfg.timestamp.column]) + pd.Timedelta(minutes=30)
            merged_30min['TIMESTAMP_END'] = end_times.dt.strftime('%Y%m%d%H%M')
            
            # Drop the original TIMESTAMP column
            merged_30min = merged_30min.drop(columns=[cfg.timestamp.column])
            
            # Replace NaN with -9999
            merged_30min = merged_30min.fillna(-9999)
            
            # Define standard column order (based on expected output format)
            standard_order = [
                'TIMESTAMP_START', 'TIMESTAMP_END',
                'TA_1_1_1', 'RH_1_1_1', 'PA_2_1_1',
                'SW_IN_1_1_1', 'SW_OUT_1_1_1', 'LW_IN_1_1_1', 'LW_OUT_1_1_1',
                'PPFD_IN_1_1_1', 'PPFD_OUT_1_1_1',
                'WS_2_1_1', 'WD_2_1_1', 'NDVI_1_1_1',
                'TS_1_1_1', 'TS_2_1_1', 'TS_1_2_1', 'TS_1_3_1', 'TS_1_4_1', 'TS_1_5_1',
                'D_SNOW_1_1_1'
            ]
            
            # Reorder columns: standard order first, then any additional columns
            ordered_cols = [col for col in standard_order if col in merged_30min.columns]
            extra_cols = [col for col in merged_30min.columns if col not in standard_order]
            merged_30min = merged_30min[ordered_cols + extra_cols]
            
            logger.info(f"Saving 30min CSV with shape {merged_30min.shape}")
            merged_30min.to_csv(str(cfg.output_path() / cfg.merge.output_30min_csv), index=False)
        except Exception as e:
            logger.warning(f"Failed to create 30min CSV: {e}")
    return merged
