
from pathlib import Path
import pandas as pd

ROOT = Path("/Users/himanshi/REGAIN")
PROCESSED = ROOT / "data" / "processed"

files = [
    "harv1_fig1b_field_displacement.csv",
    "harv1_fig1c_timeseries_unmodified.csv",
    "harv1_fig2_operating_conditions.csv",
    "harv1_fig3a_raw.csv",
    "harv1_fig3b_raw.csv",
    "harv1_preparation_report.csv",
]

for filename in files:
    path = PROCESSED / filename

    print("\n" + "=" * 75)
    print(filename)
    print("=" * 75)

    if not path.exists():
        print("FILE NOT FOUND")
        continue

    if path.stat().st_size == 0:
        print("EMPTY FILE")
        continue

    try:
        df = pd.read_csv(path, header=None if "raw.csv" in filename else "infer")
        print("Shape:", df.shape)
        print("Columns:", list(df.columns))
        print(df.head(12).to_string(index=False))
    except pd.errors.EmptyDataError:
        print("EMPTY FILE")

