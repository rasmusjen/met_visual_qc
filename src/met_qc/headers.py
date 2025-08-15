from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import csv
import logging

from .filenames import HeaderFileId, parse_header_filename

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HeaderColumn:
    column_index: int
    name: str
    units: Optional[str] = None
    notes: Optional[str] = None
    scale_factor: float = 1.0
    offset: float = 0.0


@dataclass
class HeaderTimeline:
    # key is (site, level, file)
    intervals: Dict[Tuple[str, str, str], List[Tuple[datetime, List[HeaderColumn]]]]

    def resolve(self, site: str, level: str, file: str, dt: datetime) -> Optional[List[HeaderColumn]]:
        key = (site, level, file)
        if key not in self.intervals:
            return None
        arr = self.intervals[key]
        for i, (start, cols) in enumerate(arr):
            end = arr[i + 1][0] if i + 1 < len(arr) else None
            if (dt >= start) and (end is None or dt < end):
                return cols
        return None


def _normalize_header_csv(path: Path) -> List[HeaderColumn]:
    # Flexible headers: accept various fieldnames
    # Required fields: index/column, name/variable
    field_aliases = {
        "index": {"index", "col", "column", "col_index", "column_index", "idx"},
        "name": {"name", "variable", "var", "label"},
        "units": {"units", "unit"},
        "notes": {"notes", "note", "comment", "comments"},
        "scale_factor": {"scale", "scale_factor", "mult", "factor"},
        "offset": {"offset", "add", "bias"},
    }

    def norm_key(k: str) -> Optional[str]:
        lk = k.strip().lower()
        for target, aliases in field_aliases.items():
            if lk in aliases:
                return target
        return None

    cols: List[HeaderColumn] = []
    # First, detect if file is a simple one-line header of variable names
    raw_first_row: List[str] | None = None
    with path.open("r", newline="", encoding="utf-8") as fcheck:
        r0 = csv.reader(fcheck)
        try:
            raw_first_row = next(r0)
        except StopIteration:
            raw_first_row = None
    if raw_first_row and len(raw_first_row) > 0:
        # Peek second row to see if there is data; reopen and use DictReader
        with path.open("r", newline="", encoding="utf-8") as fpeek:
            lines = fpeek.read().splitlines()
        if len(lines) == 1:
            # Single-line file: treat as names only
            names = [s.strip().strip('"') for s in raw_first_row]
            cols = [HeaderColumn(column_index=i, name=nm) for i, nm in enumerate(names)]
            return cols

    # Otherwise, parse as mapping rows with flexible column names
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Header CSV has no header row: {path}")
        keymap = {k: (norm_key(k) or k) for k in reader.fieldnames}
        for row in reader:
            data = {keymap[k]: v for k, v in row.items()}
            raw_idx = data.get("index") or data.get("column")
            if raw_idx is None:
                raise ValueError(f"Header row missing column index: {row}")
            try:
                idx = int(str(raw_idx).strip())
            except Exception as e:
                raise ValueError(f"Invalid column index: {raw_idx}") from e
            # Normalize 1-based to 0-based if it looks 1-based (common)
            if idx >= 1:
                idx = idx - 1
            name = str(data.get("name") or data.get("variable") or "").strip()
            if not name:
                raise ValueError(f"Header row missing variable name: {row}")
            units = (data.get("units") or None)
            notes = (data.get("notes") or None)
            try:
                scale = float(data.get("scale_factor") or 1.0)
            except Exception:
                scale = 1.0
            try:
                offset = float(data.get("offset") or 0.0)
            except Exception:
                offset = 0.0
            cols.append(HeaderColumn(column_index=idx, name=name, units=units, notes=notes, scale_factor=scale, offset=offset))
    cols.sort(key=lambda c: c.column_index)
    return cols


def build_header_timeline(header_dir: str) -> HeaderTimeline:
    base = Path(header_dir)
    intervals: Dict[Tuple[str, str, str], List[Tuple[datetime, List[HeaderColumn]]]] = {}
    for p in base.glob("*.csv"):
        hid = parse_header_filename(p.name)
        if not hid:
            continue
        cols = _normalize_header_csv(p)
        key = (hid.site, hid.level, hid.file)
        intervals.setdefault(key, []).append((hid.valid_from, cols))
    # Sort intervals per key
    for key in list(intervals.keys()):
        intervals[key].sort(key=lambda t: t[0])
    return HeaderTimeline(intervals=intervals)
