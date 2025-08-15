import pandas as pd


def read_csv(path):
    """Read CSV with pandas and return DataFrame. Handles common date parsing.
    """
    try:
        df = pd.read_csv(path, parse_dates=True, infer_datetime_format=True)
    except Exception:
        # fallback: read without date inference
        df = pd.read_csv(path)
    return df
