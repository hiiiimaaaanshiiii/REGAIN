
from pathlib import Path
import pandas as pd

RAW = Path("/Users/himanshi/REGAIN/data/raw")

def inspect_csv(filename):
    path = RAW / filename
    print(f"\n{'=' * 80}\n{filename}\n{'=' * 80}")

    if not path.exists():
        print("FILE NOT FOUND")
        return

    if path.stat().st_size == 0:
        print("EMPTY FILE — no columns to parse.")
        return

    try:
        df = pd.read_csv(path)
        print("Shape:", df.shape)
        print("Columns:", list(df.columns))
        print(df.head(12).to_string(index=False))
    except pd.errors.EmptyDataError:
        print("EMPTY FILE — no columns to parse.")

for filename in [
    "REGAIN_file_inventory.csv",
    "REGAIN_column_profile.csv",
    "REGAIN_numeric_summary.csv",
    "REGAIN_timestamp_diagnostics.csv",
]:
    inspect_csv(filename)

# Inspect original data directly
fig1 = RAW / "HARV1_SourceData_Fig1.xlsx"
fig2 = RAW / "HARV1_SourceData_Fig2.csv"
fig3 = RAW / "HARV1_SourceData_Fig3.xlsx"

print("\n" + "=" * 80)
print("FIG1B: FIELD-DISPLACEMENT DATA")
print("=" * 80)

df = pd.read_excel(fig1, sheet_name="Fig1b", header=None)
print(df.head(15).to_string(index=False, header=False))

# Split the semicolon-separated E;D values without losing the header
first_col = df.iloc[:, 0].astype(str)
split = first_col.str.split(";", n=1, expand=True)
print("\nParsed first rows:")
print(split.head(15).to_string(index=False, header=False))

print("\n" + "=" * 80)
print("FIG1C: TIME-SERIES DATA")
print("=" * 80)

df = pd.read_excel(fig1, sheet_name="Fig1c")
print("Columns:", list(df.columns))
print("Shape:", df.shape)
print(df.head(12).to_string(index=False))
print("\nMissing values:")
print(df.isna().sum().to_string())
print("\nValues at current limits:")
if "I(uA)" in df.columns:
    current = pd.to_numeric(df["I(uA)"], errors="coerce")
    print(df.loc[current.abs() >= 199, :].head(20).to_string(index=False))

print("\n" + "=" * 80)
print("FIG2: OPERATING-CONDITION DATA")
print("=" * 80)

df = pd.read_csv(fig2)
print(df.to_string(index=False))

print("\n" + "=" * 80)
print("FIG3: EFFICIENCY DATA")
print("=" * 80)

for sheet in ["fig3a", "fig3b"]:
    df = pd.read_excel(fig3, sheet_name=sheet, header=None)
    print(f"\n{sheet}: {df.shape}")
    print(df.head(15).to_string(index=False, header=False))
