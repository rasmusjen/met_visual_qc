from pathlib import Path
import pandas as pd
from met_qc.plotting import apply_var_min_max


def test_apply_var_min_max_remove():
    # create a simple dataframe with TIMESTAMP and P_ column
    data = {
        'TIMESTAMP': pd.date_range('2025-01-01 00:00', periods=6, freq='30T'),
        'P_RAIN': [0.0, 5.0, 12.0, 0.0, 15.0, 1.0],  # values 12 and 15 are out of range (0-10)
        'T_AIR': [10, 11, 12, 13, 14, 15]
    }
    df = pd.DataFrame(data)
    limits = [('P_', 0.0, 10.0)]
    # Remove out of range
    df_filtered, report = apply_var_min_max(df, 'TIMESTAMP', limits, ['P_RAIN'], remove=True)
    # Expect rows with values 12.0 and 15.0 removed
    assert len(df_filtered) == 4
    assert 'P_RAIN' in report
    # Ensure aggregated sums would be computed without the removed values
    # original sum = 0+5+12+0+15+1 = 33
    # filtered sum = 0+5+0+1 = 6
    assert df_filtered['P_RAIN'].sum() == 6.0
