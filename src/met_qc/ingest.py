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
            if rid.site != cfg.site_id:
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
        df = pd.read_csv(p, header=None, names=None if cfg.ingest.has_header_row else None, na_values=na_vals)
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
    # Write outputs
    cfg.output_path().mkdir(parents=True, exist_ok=True)
    merged.to_parquet(str(cfg.output_path() / cfg.merge.output_parquet), index=False)
    if cfg.merge.output_csv:
        merged.to_csv(str(cfg.output_path() / cfg.merge.output_csv), index=False)
    return merged
