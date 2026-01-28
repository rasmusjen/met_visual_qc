from __future__ import annotations
import logging
import sys
import click
import pandas as pd

from .config import load_config
from .headers import build_header_timeline
from .ingest import ingest_and_merge
from .plotting import build_qc_dashboards

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


@click.group()
def cli() -> None:
    """met-qc: process, merge, and plot meteorological QC data."""


def _parse_date_token(token: str):
    token = token.strip()
    if len(token) == 4:
        # year only
        from datetime import date
        y = int(token)
        return date(y, 1, 1), date(y, 12, 31)
    elif len(token) == 8:
        from datetime import datetime
        d = datetime.strptime(token, "%Y%m%d").date()
        return d, d
    else:
        raise click.BadParameter("Date must be YYYY or YYYYMMDD")


@cli.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True))
@click.option("--year", type=str, required=False, help="Year to load, e.g., 2025")
@click.option("--from", "from_", type=str, required=False, help="Start date YYYYMMDD")
@click.option("--to", type=str, required=False, help="End date YYYYMMDD (inclusive)")
def process(config_path: str, year: str | None, from_: str | None, to: str | None) -> None:
    cfg = load_config(config_path)
    tl = build_header_timeline(cfg.header_dir)
    # Merge precedence: CLI > YAML range
    y = year or cfg.range.year
    f = from_ or cfg.range.from_
    t = to or cfg.range.to
    dfrom = dto = None
    if y:
        dfrom, dto = _parse_date_token(y)
    if f:
        dfrom = _parse_date_token(f)[0]
    if t:
        dto = _parse_date_token(t)[1]
    df = ingest_and_merge(cfg, tl, date_from=dfrom, date_to=dto)
    click.echo(f"Merged rows: {len(df)} -> {cfg.output_dir}")


@cli.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True))
@click.option("--year", type=str, required=False)
@click.option("--from", "from_", type=str, required=False)
@click.option("--to", type=str, required=False)
def plot(config_path: str, year: str | None, from_: str | None, to: str | None) -> None:
    cfg = load_config(config_path)
    # Read merged parquet
    df = pd.read_parquet(f"{cfg.output_dir}/{cfg.merge.output_parquet}")
    ts = cfg.timestamp.column
    y = year or cfg.range.year
    f = from_ or cfg.range.from_
    t = to or cfg.range.to
    dfrom = dto = None
    if y:
        dfrom, dto = _parse_date_token(y)
    if f:
        dfrom = _parse_date_token(f)[0]
    if t:
        dto = _parse_date_token(t)[1]
    if dfrom:
        df = df[df[ts] >= pd.Timestamp(dfrom)]
    if dto:
        df = df[df[ts] <= pd.Timestamp(dto) + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)]
    build_qc_dashboard(cfg, df)
    click.echo(f"Wrote {cfg.plot.output_html} to {cfg.output_dir}")


@cli.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True))
@click.option("--year", type=str, required=False)
@click.option("--from", "from_", type=str, required=False)
@click.option("--to", type=str, required=False)
def all(config_path: str, year: str | None, from_: str | None, to: str | None) -> None:
    cfg = load_config(config_path)
    tl = build_header_timeline(cfg.header_dir)
    y = year or cfg.range.year
    f = from_ or cfg.range.from_
    t = to or cfg.range.to
    dfrom = dto = None
    if y:
        dfrom, dto = _parse_date_token(y)
    if f:
        dfrom = _parse_date_token(f)[0]
    if t:
        dto = _parse_date_token(t)[1]
    df = ingest_and_merge(cfg, tl, date_from=dfrom, date_to=dto)
    paths = build_qc_dashboards(cfg, df)
    for p in paths:
        click.echo(f"Generated: {p}")


def main() -> None:
    cli.main(standalone_mode=False)


if __name__ == "__main__":
    main()
