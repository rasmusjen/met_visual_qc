"""met_qc package: ingest daily .dat files, apply headers, and plot QC.

Public API is intentionally small and oriented around pure, testable functions.
"""
from .config import QCConfig, load_config
from .filenames import parse_raw_filename, parse_header_filename, RawFileId, HeaderFileId
from .headers import HeaderTimeline, HeaderColumn, build_header_timeline
from .ingest import ingest_and_merge
from .plotting import build_qc_dashboard

__all__ = [
    "QCConfig",
    "load_config",
    "parse_raw_filename",
    "parse_header_filename",
    "RawFileId",
    "HeaderFileId",
    "HeaderTimeline",
    "HeaderColumn",
    "build_header_timeline",
    "ingest_and_merge",
    "build_qc_dashboard",
]
