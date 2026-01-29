import pandas as pd
import plotly.graph_objects as go
import plotly.subplots as sp
from pathlib import Path

# Read both files
ref = pd.read_csv(r'output\ZaH\Met_2024\GL-ZaH_BM_20240101-20240916.csv')
combined = pd.read_csv(r'output\ZaH\Met_2024\merged_30min_combined.csv')

# Replace -9999 with NaN for plotting (in-memory only, doesn't modify files)
ref = ref.replace(-9999, pd.NA)
combined = combined.replace(-9999, pd.NA)

# Convert timestamp columns to datetime
ref['TIMESTAMP_START'] = pd.to_datetime(ref['TIMESTAMP_START'], format='%Y%m%d%H%M')
ref['TIMESTAMP_END'] = pd.to_datetime(ref['TIMESTAMP_END'], format='%Y%m%d%H%M')
combined['TIMESTAMP_START'] = pd.to_datetime(combined['TIMESTAMP_START'], format='%Y%m%d%H%M')
combined['TIMESTAMP_END'] = pd.to_datetime(combined['TIMESTAMP_END'], format='%Y%m%d%H%M')

# Find common variables (exclude timestamp columns and internal use columns)
skip_cols = ['TIMESTAMP_START', 'TIMESTAMP_END']
skip_prefixes = ('_IU_',)
ref_vars = [c for c in ref.columns if c not in skip_cols and not any(p in c for p in skip_prefixes)]
common_vars = [v for v in ref_vars if v in combined.columns]

print(f"Reference file: {len(ref)} rows")
print(f"Combined file: {len(combined)} rows")
print(f"Common variables: {len(common_vars)}")
print(f"Variables: {common_vars}\n")

# Create subplots
nvars = len(common_vars)
fig = sp.make_subplots(
    rows=nvars, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.005,
    subplot_titles=[f"{v} (30min)" for v in common_vars],
    row_heights=[1] * nvars
)

# Add traces for each variable
current_row = 1
for var in common_vars:
    # Add reference file trace
    fig.add_trace(
        go.Scatter(
            x=ref['TIMESTAMP_START'],
            y=ref[var],
            mode='lines',
            name=var + ' (Reference)',
            line=dict(color='blue', width=1),
            legendgroup=var,
            showlegend=(current_row == 1)
        ),
        row=current_row, col=1
    )
    
    # Add combined file trace
    fig.add_trace(
        go.Scatter(
            x=combined['TIMESTAMP_START'],
            y=combined[var],
            mode='lines',
            name=var + ' (Combined)',
            line=dict(color='red', width=1),
            legendgroup=var,
            showlegend=(current_row == 1)
        ),
        row=current_row, col=1
    )
    
    current_row += 1

# Update layout
fig.update_layout(
    height=200 * nvars,
    title_text="Comparison: Reference vs Merged 30min Data",
    hovermode='x unified',
    template='plotly',
    font=dict(size=10)
)

# Update y-axis labels
for i, var in enumerate(common_vars, 1):
    fig.update_yaxes(title_text=var, row=i, col=1)

# Save to HTML
output_path = Path(r'output\ZaH\Met_2024\comparison_30min.html')
fig.write_html(str(output_path))
print(f"Saved comparison plot to: {output_path}")
