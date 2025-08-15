# met_visual_qc / met_qc

[![Python tests](https://github.com/rasmusjen/met_visual_qc/actions/workflows/python-tests.yml/badge.svg)](https://github.com/rasmusjen/met_visual_qc/actions/workflows/python-tests.yml)

Lightweight tools to ingest, visually inspect and quality-control meteorological time-series files.

This repository contains two related utilities:

- `met_visual_qc`: small helpers for quick CSV plotting and inspection.
- `met_qc`: a configuration-driven pipeline that ingests daily `.dat` files (with separate header CSVs), merges them into a time-indexed dataset, and creates an interactive Plotly HTML QC report.

## Quick start (PowerShell)

1. Create and activate an environment (recommended: conda or venv):

```powershell
# conda (recommended)
conda create -n met_visual_qc python=3.11 -y; conda activate met_visual_qc

# or venv
python -m venv .venv; .\.venv\Scripts\Activate.ps1
```

1. Install dependencies and the package in editable mode:

```powershell
pip install -r requirements.txt
pip install -e .
```

1. Run the pipeline on the example config:

```powershell
python -m met_qc.cli all --config config\example_config.yaml
```

Notes:

- If you use conda, you can run the CLI inside the env directly or with `conda run -n met_visual_qc ...` when automating.

## What the pipeline does

- Scans `input_dir` for files matching the strict pattern `site_BM_YYYYMMDD_Lxx_Fyy.dat`.
- Matches header CSVs named `site_BMHEADER_YYYYMMDDHHMM_Lxx_Fyy.csv` to raw data using a header timeline.
- Applies header mappings (names, units, scale/offset) when ingesting each file.
- Concatenates, coerces types, deduplicates, and saves merged data to `output/`.
- Produces an interactive HTML QC report with:
  - Raw time series, 30‑minute and daily aggregates (sum for variables starting with `P_`, mean otherwise).
  - Missing-data heatmap and per-file coverage (stacked bars per day).
  - An "Out-of-range values" list (based on `config/var_min_max.csv`).
  - Monthly and whole-period summary table when the plotted data span > 1 month.

## Important configuration options

- `config/example_config.yaml` and `config/2025_precip_config.yaml` show examples.
- Key fields in the YAML (`QCConfig`):
  - `input_dir`: folder with raw `.dat` files.
  - `header_dir`: folder with header CSVs.
  - `output_dir`: folder where `merged.parquet` and `qc_overview.html` are written.
  - `filters.logger_file`: optional logger selector (e.g. `L05_F02`) — only files matching this logger are processed when set.
  - `plot.plot_filter`: when true, raw samples outside configured min/max are removed from plots and from aggregated resampling; they are still listed under "Out-of-range values".
  - `plot.variables_include`: optional list to restrict plotted variables.

  Minimal example `config/example_config.yaml` (copy-paste and adapt):

  ```yaml
  # minimal example_config.yaml
  input_dir: "examples"
  header_dir: "config/headers"
  output_dir: "output"
  site_id: "GL-ZaF"
  file_glob: "*.dat"
  filters:
    logger_file: "L05_F02"  # optional: only process files from this logger
  plot:
    output_html: "qc_overview.html"
    plot_filter: false       # if true, remove out-of-range raw samples from plots and aggregates
    resample: null
    include_missing_heatmap: true
    include_file_coverage: true
  timestamp:
    column: "TIMESTAMP"
    raw_format: "%Y%m%d%H%M"
  range:
    year: "2025"
  ```

## Variable min/max screening

- The file `config/var_min_max.csv` is used to declare per-variable limits. It expects columns `Variable,Min,Max`.
- A row where `Variable` ends with `_` is treated as a prefix. Example: `P_,0,10` applies `Min=0` and `Max=10` to all variables starting with `P_`.

## Filenames and header mapping rules

- Only files matching the strict patterns are considered; this avoids accidental processing of unrelated files.
- Raw filename example: `GL-ZaF_BM_20241105_L05_F02.dat`.
- Header filename example: `GL-ZaF_BMHEADER_202305061856_L05_F02.csv`.

## Outputs

- `output/merged.parquet` — merged dataset (column names as in headers, timestamp column defined by the config).
- `output/qc_overview.html` — interactive report with plots, missing-data heatmap, file coverage, out-of-range list, and monthly/whole-period summary (if applicable).

## Running tests

Run the test suite from the project root after installing the package:

```powershell
python -m pytest -q
```

There is also a VS Code task `Run tests` that installs the package in editable mode and runs pytest.

## Development notes

- The project is intentionally configuration-driven. See `src/met_qc/config.py` for the typed dataclasses that define the YAML structure.
- Important helpers:
  - `src/met_qc/filenames.py` — strict filename parsing.
  - `src/met_qc/headers.py` — header normalization and timeline mapping.
  - `src/met_qc/ingest.py` — ingest and merge pipeline.
  - `src/met_qc/plotting.py` — Plotly dashboard builder (includes screening, monthly summary injection, and HTML generation).

## Troubleshooting

- If the CLI errors with "Python was not found" in VS Code terminals, ensure the `met_visual_qc` environment is activated, or run with `conda run -n met_visual_qc python -m met_qc.cli ...`.
- If you change the config dataclasses in `src/met_qc/config.py`, update example YAMLs in `config/` accordingly.

## Contributing

Contributions, bug reports and small enhancements are welcome. Open an issue or submit a PR with focused changes and tests.

## License

See `PKG-INFO` in the project root for packaging metadata; include an explicit license file if you plan to publish.
