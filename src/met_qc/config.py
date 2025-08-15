from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import yaml
from pathlib import Path


@dataclass
class TimestampCfg:
    column: str
    raw_format: str
    timezone: Optional[str] = None


@dataclass
class IngestCfg:
    has_header_row: bool = False
    nan_values: List[str] = field(default_factory=lambda: ["-9999", "-9999.0", "NA", "NaN", ""]) 
    coerce_numeric: bool = True


@dataclass
class MergeCfg:
    sort_by_timestamp: bool = True
    drop_duplicates: bool = True
    output_parquet: str = "merged.parquet"
    output_csv: Optional[str] = None


@dataclass
class PlotCfg:
    resample: Optional[str] = None
    variables_include: List[str] = field(default_factory=list)
    output_html: str = "qc_overview.html"
    include_missing_heatmap: bool = True
    include_file_coverage: bool = True


@dataclass
class FiltersCfg:
    level_code: Optional[str] = None
    file_code: Optional[str] = None


@dataclass
class RangeCfg:
    year: Optional[str] = None  # e.g., "2025"
    from_: Optional[str] = None  # e.g., "20250101"
    to: Optional[str] = None     # e.g., "20250314"


@dataclass
class QCConfig:
    site_id: str
    input_dir: str
    header_dir: str
    output_dir: str
    file_glob: str = "*.dat"
    filters: FiltersCfg = field(default_factory=FiltersCfg)
    timestamp: TimestampCfg = field(default_factory=lambda: TimestampCfg(column="TIMESTAMP", raw_format="%Y%m%d%H%M", timezone="UTC"))
    ingest: IngestCfg = field(default_factory=IngestCfg)
    merge: MergeCfg = field(default_factory=MergeCfg)
    plot: PlotCfg = field(default_factory=PlotCfg)
    range: RangeCfg = field(default_factory=RangeCfg)

    def output_path(self) -> Path:
        return Path(self.output_dir)


def _as_filters(d: Dict[str, Any]) -> FiltersCfg:
    return FiltersCfg(level_code=d.get("level_code"), file_code=d.get("file_code"))


def _as_timestamp(d: Dict[str, Any]) -> TimestampCfg:
    return TimestampCfg(column=d["column"], raw_format=d["raw_format"], timezone=d.get("timezone"))


def _as_ingest(d: Dict[str, Any]) -> IngestCfg:
    return IngestCfg(
        has_header_row=bool(d.get("has_header_row", False)),
        nan_values=list(d.get("nan_values", ["-9999", "-9999.0", "NA", "NaN", ""])),
        coerce_numeric=bool(d.get("coerce_numeric", True)),
    )


def _as_merge(d: Dict[str, Any]) -> MergeCfg:
    return MergeCfg(
        sort_by_timestamp=bool(d.get("sort_by_timestamp", True)),
        drop_duplicates=bool(d.get("drop_duplicates", True)),
        output_parquet=str(d.get("output_parquet", "merged.parquet")),
        output_csv=d.get("output_csv"),
    )


def _as_plot(d: Dict[str, Any]) -> PlotCfg:
    return PlotCfg(
        resample=d.get("resample"),
        variables_include=list(d.get("variables_include", [])),
        output_html=str(d.get("output_html", "qc_overview.html")),
        include_missing_heatmap=bool(d.get("include_missing_heatmap", True)),
        include_file_coverage=bool(d.get("include_file_coverage", True)),
    )


def _as_range(d: Dict[str, Any]) -> RangeCfg:
    # YAML keys: year, from, to
    return RangeCfg(
        year=(str(d.get("year")) if d.get("year") is not None else None),
        from_=(str(d.get("from")) if d.get("from") is not None else None),
        to=(str(d.get("to")) if d.get("to") is not None else None),
    )


def load_config(path: str | Path) -> QCConfig:
    p = Path(path)
    data = yaml.safe_load(p.read_text())
    return QCConfig(
        site_id=str(data["site_id"]),
        input_dir=str(data["input_dir"]),
        header_dir=str(data["header_dir"]),
        output_dir=str(data["output_dir"]),
        file_glob=str(data.get("file_glob", "*.dat")),
        filters=_as_filters(data.get("filters", {})),
        timestamp=_as_timestamp(data.get("timestamp", {})),
        ingest=_as_ingest(data.get("ingest", {})),
        merge=_as_merge(data.get("merge", {})),
        plot=_as_plot(data.get("plot", {})),
        range=_as_range(data.get("range", {})),
    )
