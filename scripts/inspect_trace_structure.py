
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("/Users/himanshi/REGAIN")
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

df = pd.read_excel(
    RAW / "HARV1_SourceData_Fig1.xlsx",
    sheet_name="Fig1c"
)

for col in ["t(s)", "V(V)", "I(uA)", "E(mj)"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

print("\n=== ORIGINAL ROWS AROUND THE MISSING-DATA TRANSITION ===")
print(df.iloc[3085:3120].to_string())

print("\n=== MISSINGNESS PATTERNS ===")
missing = df[["t(s)", "V(V)", "I(uA)", "E(mj)"]].isna()
print(missing.value_counts().to_string())

print("\n=== CONTIGUOUS MISSINGNESS REGIONS ===")
pattern = missing.astype(str).agg("|".join, axis=1)
group = pattern.ne(pattern.shift()).cumsum()

regions = df.assign(pattern=pattern, group=group).groupby("group").agg(
    start_row=("group", lambda x: x.index.min()),
    end_row=("group", lambda x: x.index.max()),
    rows=("group", "size"),
    start_time=("t(s)", "first"),
    end_time=("t(s)", "last"),
    pattern=("pattern", "first")
)
print(regions.to_string())

print("\n=== TIME-DIFFERENCE DISTRIBUTION ===")
dt = df["t(s)"].diff()
print(dt.describe().to_string())
print("Negative differences:", int((dt < 0).sum()))
print("Zero differences:", int((dt == 0).sum()))
print("Positive differences:", int((dt > 0).sum()))

print("\n=== TIME RESET LOCATIONS ===")
reset = dt < 0
print(df.loc[reset, ["t(s)", "V(V)", "I(uA)", "E(mj)"]].head(30).to_string())

regions.to_csv(OUT / "harv1_missingness_regions.csv")
print("\nSaved:", OUT / "harv1_missingness_regions.csv")

