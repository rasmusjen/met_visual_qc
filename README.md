# met_visual_qc / met_qc

Tools to visually QC meteorological data files.

## Components

- `met_visual_qc`: simple CSV plotting utilities.
- `met_qc`: ingest daily `.dat` files with external headers, merge, and produce interactive Plotly QC HTML.

## Quick start (PowerShell)

1. Create and activate an environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

1. Install

```powershell
pip install -r requirements.txt
pip install -e .
```

1. Run the new CLI on example data

```powershell
python -m met_qc.cli all --config config\example_config.yaml
```

## Artifacts

- Merged parquet in `output/merged.parquet`
- QC HTML at `output/qc_overview.html`

## Persisted date range (optional)

- Set in `config/example_config.yaml` under `range:`
  - `year: "2025"` or `from: "20250101"` / `to: "20250314"`
- CLI flags `--year/--from/--to` override the YAML values when provided.
