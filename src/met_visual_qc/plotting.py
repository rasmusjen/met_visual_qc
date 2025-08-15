import matplotlib.pyplot as plt
import seaborn as sns
import os


def quick_plot(df, cols=None, out_dir='outputs', show=False):
    """Create simple line plots for numeric columns in `cols` or all numeric columns.
    Saves PNGs to out_dir. If show=True, displays the plot.
    """
    if cols is None:
        cols = df.select_dtypes(include='number').columns.tolist()
    for col in cols:
        if col not in df.columns:
            continue
        plt.figure(figsize=(10,4))
        sns.lineplot(data=df, x=df.index, y=col)
        plt.title(f"{col}")
        fname = os.path.join(out_dir, f"{col}.png")
        plt.tight_layout()
        plt.savefig(fname)
        if show:
            plt.show()
        plt.close()
