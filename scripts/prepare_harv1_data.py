
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("/Users/himanshi/REGAIN")
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

FIG1 = RAW / "HARV1_SourceData_Fig1.xlsx"
FIG2 = RAW / "HARV1_SourceData_Fig2.csv"
FIG3 = RAW / "HARV1_SourceData_Fig3.xlsx"

report = []

def log(dataset, check, result, details=""):
    report.append({
        "dataset": dataset,
        "check": check,
        "result": result,
        "details": str(details)
    })

# --------------------------------------------------
# 1. Fig1b: Parse field-displacement measurements
# --------------------------------------------------
raw = pd.read_excel(FIG1, sheet_name="Fig1b", header=None)
first = raw.iloc[:, 0].astype("string").str.strip()

# Preserve temperature/header rows separately
parts = first.str.split(";", n=1, expand=True)
parsed = pd.DataFrame({
    "raw_value": first,
    "E_kV_cm": pd.to_numeric(parts[0], errors="coerce"),
    "D_uC_cm2": pd.to_numeric(
        parts[1] if parts.shape[1] > 1 else pd.Series(
            pd.NA, index=parts.index, dtype="string"
        ),
        errors="coerce"
    )
})

valid = parsed[["E_kV_cm", "D_uC_cm2"]].notna().all(axis=1)
fig1b = parsed.loc[valid, ["E_kV_cm", "D_uC_cm2"]].copy()
fig1b.to_csv(PROCESSED / "harv1_fig1b_field_displacement.csv", index=False)

log("Fig1b", "Rows read", len(raw))
log("Fig1b", "Parsed numeric pairs", int(valid.sum()))
log("Fig1b", "Unparsed rows", int((~valid).sum()),
    "Inspect raw_value before deciding whether rows are headers or data.")

# --------------------------------------------------
# 2. Fig1c: Time-series measurements
# --------------------------------------------------
fig1c = pd.read_excel(FIG1, sheet_name="Fig1c")
fig1c.columns = [str(c).strip() for c in fig1c.columns]

expected = ["t(s)", "V(V)", "I(uA)", "E(mj)"]
missing_cols = [c for c in expected if c not in fig1c.columns]

if missing_cols:
    log("Fig1c", "Expected columns", "CHECK",
        f"Missing columns: {missing_cols}; found {list(fig1c.columns)}")
else:
    for col in expected:
        fig1c[col] = pd.to_numeric(fig1c[col], errors="coerce")

    log("Fig1c", "Rows", len(fig1c))
    log("Fig1c", "Missing values", "CHECK",
        fig1c[expected].isna().sum().to_dict())

    # Do not impute or clip missing/current-limit values.
    log("Fig1c", "Current at +/-200 uA",
        int(fig1c["I(uA)"].abs().ge(199.999).sum()),
        "Potential measurement limit; verify against paper and instrument metadata.")
    log("Fig1c", "Time monotonic",
        bool(fig1c["t(s)"].dropna().is_monotonic_increasing))
    log("Fig1c", "Duplicate timestamps",
        int(fig1c["t(s)"].dropna().duplicated().sum()))

    fig1c.to_csv(PROCESSED / "harv1_fig1c_timeseries_unmodified.csv",
                 index=False)

# --------------------------------------------------
# 3. Fig2: Operating-condition measurements
# --------------------------------------------------
fig2 = pd.read_csv(FIG2)
fig2.columns = [str(c).strip() for c in fig2.columns]

for col in fig2.columns:
    fig2[col] = pd.to_numeric(fig2[col], errors="coerce")

fig2.to_csv(PROCESSED / "harv1_fig2_operating_conditions.csv", index=False)
log("Fig2", "Rows", len(fig2))
log("Fig2", "Columns", list(fig2.columns))
log("Fig2", "Missing values", "CHECK", fig2.isna().sum().to_dict())

# --------------------------------------------------
# 4. Fig3: Efficiency-related data
# --------------------------------------------------
for sheet in ["fig3a", "fig3b"]:
    df = pd.read_excel(FIG3, sheet_name=sheet, header=None)
    df.to_csv(PROCESSED / f"harv1_{sheet}_raw.csv", index=False, header=False)
    log(sheet, "Rows", len(df))
    log(sheet, "First rows", "REVIEW",
        df.head(5).to_dict(orient="records"))

# --------------------------------------------------
# 5. Save audit report
# --------------------------------------------------
report_df = pd.DataFrame(report)
report_path = PROCESSED / "harv1_preparation_report.csv"
report_df.to_csv(report_path, index=False)

print("\nHARV1 DATA PREPARATION COMPLETE")
print("Processed directory:", PROCESSED)
print("\nPreparation report:")
print(report_df.to_string(index=False))
print("\nFiles created:")
for p in sorted(PROCESSED.iterdir()):
    print(p.name, f"({p.stat().st_size:,} bytes)")

