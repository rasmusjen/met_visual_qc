import pandas as pd

# Process 2024 data
print("=== Processing 2024 data ===")
# Read Met and Soil_snow data
met_merged = pd.read_csv(r'output\ZaH\Met_2024\merged.csv')
soil_merged = pd.read_csv(r'output\ZaH\Soil_snow_2024\merged.csv')

met_30min = pd.read_csv(r'output\ZaH\Met_2024\merged_30min.csv')
soil_30min = pd.read_csv(r'output\ZaH\Soil_snow_2024\merged_30min.csv')

# Merge regular merged files on TIMESTAMP
print("Met columns:", list(met_merged.columns))
print("Soil columns:", list(soil_merged.columns))
print("Met shape:", met_merged.shape)
print("Soil shape:", soil_merged.shape)

merged_combined = pd.merge(met_merged, soil_merged, on='TIMESTAMP', how='outer')
print("\nMerged combined shape:", merged_combined.shape)

# Reorder columns: Met columns first, then Soil columns
met_cols = [c for c in merged_combined.columns if c in met_merged.columns]
soil_cols = [c for c in merged_combined.columns if c in soil_merged.columns and c != 'TIMESTAMP']
ordered_cols = met_cols + soil_cols
merged_combined = merged_combined[ordered_cols]

merged_combined.to_csv(r'output\ZaH\Met_2024\merged_combined.csv', index=False)
print("Saved merged.csv")

# Do the same for 30min - merge on TIMESTAMP_START and TIMESTAMP_END
print("\n\nMet 30min columns:", list(met_30min.columns))
print("Soil 30min columns:", list(soil_30min.columns))

merged_30min_combined = pd.merge(met_30min, soil_30min, on=['TIMESTAMP_START', 'TIMESTAMP_END'], how='outer')
print("Merged 30min combined shape:", merged_30min_combined.shape)

# Reorder columns: Met columns first (excluding duplicate timestamp cols), then Soil columns
met_30_cols = [c for c in met_30min.columns]
soil_30_cols = [c for c in soil_30min.columns if c not in ['TIMESTAMP_START', 'TIMESTAMP_END']]
ordered_30_cols = met_30_cols + soil_30_cols
merged_30min_combined = merged_30min_combined[ordered_30_cols]

merged_30min_combined.to_csv(r'output\ZaH\Met_2024\merged_30min_combined.csv', index=False)
print("Saved merged_30min.csv")

print("\n=== Processing 2025 data ===")
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
