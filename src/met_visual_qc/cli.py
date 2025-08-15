import click
from .reader import read_csv
from .plotting import quick_plot
import os

@click.command()
@click.argument('csv_path', type=click.Path(exists=True))
@click.option('--y', '-y', help='Comma-separated list of columns to plot', default=None)
@click.option('--out', '-o', help='Output directory for plots', default='outputs')
@click.option('--show/--no-show', default=False, help='Show plots interactively')
def main(csv_path, y, out, show):
    os.makedirs(out, exist_ok=True)
    df = read_csv(csv_path)
    cols = None if y is None else [c.strip() for c in y.split(',')]
    quick_plot(df, cols=cols, out_dir=out, show=show)

if __name__ == '__main__':
    main()
