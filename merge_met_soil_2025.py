import pandas as pd

print("=== Processing 2025 data ===")
# Read Met and Soil_snow data for 2025
met_merged_25 = pd.read_csv(r'output\ZaH\Met_2025\merged.csv')
soil_merged_25 = pd.read_csv(r'output\ZaH\Soil_snow_2025\merged.csv')

met_30min_25 = pd.read_csv(r'output\ZaH\Met_2025\merged_30min.csv')
soil_30min_25 = pd.read_csv(r'output\ZaH\Soil_snow_2025\merged_30min.csv')

# Merge regular merged files on TIMESTAMP
print("Met shape:", met_merged_25.shape)
print("Soil shape:", soil_merged_25.shape)

merged_combined_25 = pd.merge(met_merged_25, soil_merged_25, on='TIMESTAMP', how='outer')
print("Merged combined shape:", merged_combined_25.shape)

# Reorder columns: Met columns first, then Soil columns
met_cols_25 = [c for c in merged_combined_25.columns if c in met_merged_25.columns]
soil_cols_25 = [c for c in merged_combined_25.columns if c in soil_merged_25.columns and c != 'TIMESTAMP']
ordered_cols_25 = met_cols_25 + soil_cols_25
merged_combined_25 = merged_combined_25[ordered_cols_25]

merged_combined_25.to_csv(r'output\ZaH\Met_2025\merged_combined.csv', index=False)
print("Saved 2025 merged.csv")

# Do the same for 30min
merged_30min_combined_25 = pd.merge(met_30min_25, soil_30min_25, on=['TIMESTAMP_START', 'TIMESTAMP_END'], how='outer')
print("Merged 30min combined shape:", merged_30min_combined_25.shape)

# Reorder columns: Met columns first, then Soil columns
met_30_cols_25 = [c for c in met_30min_25.columns]
soil_30_cols_25 = [c for c in soil_30min_25.columns if c not in ['TIMESTAMP_START', 'TIMESTAMP_END']]
ordered_30_cols_25 = met_30_cols_25 + soil_30_cols_25
merged_30min_combined_25 = merged_30min_combined_25[ordered_30_cols_25]

merged_30min_combined_25.to_csv(r'output\ZaH\Met_2025\merged_30min_combined.csv', index=False)
print("Saved 2025 merged_30min.csv")

print("\nDone!")
