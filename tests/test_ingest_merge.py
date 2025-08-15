from pathlib import Path
import pandas as pd
from met_qc.config import load_config
from met_qc.headers import build_header_timeline
from met_qc.ingest import ingest_and_merge


def test_ingest_merge_examples(tmp_path: Path):
    # Use provided examples directory and header
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
site_id: "GL-ZaF"
input_dir: "examples"
header_dir: "examples"
output_dir: "output"
file_glob: "*.dat"
filters:
  level_code: "L05"
  file_code: "F02"
timestamp:
  column: "TIMESTAMP"
  raw_format: "%Y%m%d%H%M"
  timezone: "UTC"
ingest:
  has_header_row: false
  nan_values: ["-9999", "-9999.0", "NA", "NaN", ""]
  coerce_numeric: true
merge:
  sort_by_timestamp: true
  drop_duplicates: true
  output_parquet: "merged.parquet"
  output_csv: "merged.csv"
plot:
  resample: null
  variables_include: []
  output_html: "qc_overview.html"
  include_missing_heatmap: true
  include_file_coverage: true
        """
    )
    cfg = load_config(cfg_path)
    tl = build_header_timeline(cfg.header_dir)
    df = ingest_and_merge(cfg, tl)
    assert not df.empty
    assert "TIMESTAMP" in df.columns
    assert df["TIMESTAMP"].is_monotonic_increasing
    # outputs exist
    assert (Path(cfg.output_dir) / cfg.merge.output_parquet).exists()
