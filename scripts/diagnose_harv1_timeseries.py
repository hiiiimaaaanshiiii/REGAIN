
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("/Users/himanshi/REGAIN")
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

path = RAW / "HARV1_SourceData_Fig1.xlsx"
df = pd.read_excel(path, sheet_name="Fig1c")

# Preserve original row order and add a traceable row index
df.insert(0, "source_row", np.arange(len(df)))
for col in ["t(s)", "V(V)", "I(uA)", "E(mj)"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

t = df["t(s)"]
dt = t.diff()

print("\n=== BASIC DIAGNOSTICS ===")
print("Rows:", len(df))
print("Missing time:", t.isna().sum())
print("Duplicate non-missing timestamps:", t.dropna().duplicated().sum())
print("Negative time differences:", (dt < 0).sum())
print("Zero time differences:", (dt == 0).sum())
print("Positive time differences:", (dt > 0).sum())
print("Time range:", t.min(), "to", t.max(), "seconds")

print("\n=== FIRST 25 TIME DIFFERENCES ===")
print(df[["source_row", "t(s)", "V(V)", "I(uA)", "E(mj)"]]
      .assign(delta_t=dt).head(25).to_string(index=False))

# Show locations where time decreases or repeats
change = dt.notna() & (dt <= 0)
problem_rows = df.loc[change, ["source_row", "t(s)", "V(V)", "I(uA)", "E(mj)"]].copy()
problem_rows["previous_t"] = t.shift(1).loc[change]
problem_rows["delta_t"] = dt.loc[change]

print("\n=== FIRST 40 NON-INCREASING TIME ROWS ===")
print(problem_rows.head(40).to_string(index=False))

problem_rows.to_csv(OUT / "harv1_fig1c_nonincreasing_time_rows.csv", index=False)

# Report consecutive time blocks without changing row order.
# A new block starts at missing time or when time fails to increase.
block_id = (t.isna() | (dt <= 0)).cumsum()
df["time_block"] = block_id

print("\n=== TIME BLOCKS ===")
blocks = (
    df.groupby("time_block", dropna=False)
      .agg(
          rows=("source_row", "size"),
          first_source_row=("source_row", "min"),
          last_source_row=("source_row", "max"),
          first_time_s=("t(s)", "first"),
          last_time_s=("t(s)", "last"),
          missing_current=("I(uA)", lambda x: x.isna().sum()),
          missing_energy=("E(mj)", lambda x: x.isna().sum()),
      )
      .reset_index()
)
print(blocks.to_string(index=False))
blocks.to_csv(OUT / "harv1_fig1c_time_blocks.csv", index=False)

# Keep a complete diagnostic copy; no rows removed, no imputation.
df.to_csv(OUT / "harv1_fig1c_time_diagnostics.csv", index=False)

print("\nSaved:")
print(OUT / "harv1_fig1c_nonincreasing_time_rows.csv")
print(OUT / "harv1_fig1c_time_blocks.csv")
print(OUT / "harv1_fig1c_time_diagnostics.csv")

