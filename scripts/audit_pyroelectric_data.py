
#!/usr/bin/env python3
"""
REGAIN: Pyroelectric Experimental Data Audit

Supported inputs:
    .csv, .xlsx, .xlsm

Outputs:
    REGAIN_data_audit.xlsx
    REGAIN_file_inventory.csv
    REGAIN_column_profile.csv
    REGAIN_numeric_summary.csv
    REGAIN_timestamp_diagnostics.csv

Usage:
    python3 audit_pyroelectric_data.py --folder /path/to/REGAIN/data/raw
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from pathlib import Path
from typing import Any

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xlsm"}
OUTPUT_PREFIX = "REGAIN_"

TIMESTAMP_HINTS = (
    "timestamp", "datetime", "date_time", "date time",
    "time_stamp", "date", "time",
)

PHYSICS_HINTS = (
    "temperature", "temp", "voltage", "current",
    "electric field", "field", "displacement",
    "polarization", "polarisation", "power", "energy",
    "frequency", "heat", "flow", "pressure",
    "efficiency", "cycle", "capacitance", "resistance",
)


def clean_name(value: Any) -> str:
    if pd.isna(value):
        return "(blank column name)"
    name = str(value).strip()
    return name if name else "(blank column name)"


def serializable(value: Any) -> Any:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass

    if isinstance(value, float) and not math.isfinite(value):
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def read_csv_safely(path: Path) -> pd.DataFrame:
    """Read CSV with delimiter detection and encoding fallbacks.

    Important fix:
    low_memory is deliberately omitted because it is unsupported
    when pandas uses engine='python'.
    """
    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
    errors = []

    for encoding in encodings:
        try:
            return pd.read_csv(
                path,
                sep=None,
                engine="python",
                encoding=encoding,
                on_bad_lines="warn",
            )
        except (
            UnicodeDecodeError,
            pd.errors.ParserError,
            ValueError,
            OSError,
        ) as exc:
            errors.append(f"{encoding}: {exc}")

    raise RuntimeError(
        "Could not parse CSV:\n" + "\n".join(errors)
    )


def load_table(
    path: Path,
    sheet_name: str | None = None,
) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return read_csv_safely(path)

    return pd.read_excel(
        path,
        sheet_name=sheet_name,
        header=0,
        engine="openpyxl",
    )


def find_timestamp_columns(df: pd.DataFrame) -> list[str]:
    result = []

    for column in df.columns:
        name = str(column).strip().lower()
        if any(hint in name for hint in TIMESTAMP_HINTS):
            result.append(column)

    return result


def audit_timestamps(
    df: pd.DataFrame,
    file_name: str,
    sheet_name: str,
) -> list[dict[str, Any]]:
    records = []

    for column in find_timestamp_columns(df):
        parsed = pd.to_datetime(
            df[column],
            errors="coerce",
            format="mixed",
        )
        valid = parsed.dropna()

        record = {
            "file": file_name,
            "sheet": sheet_name,
            "column": str(column),
            "rows": len(df),
            "parsed_timestamp_count": len(valid),
            "unparsed_count": int(parsed.isna().sum()),
            "parse_success_fraction": (
                len(valid) / len(df) if len(df) else None
            ),
            "duplicate_timestamp_count": (
                int(valid.duplicated().sum()) if len(valid) else None
            ),
            "non_monotonic_count": None,
            "first_timestamp": None,
            "last_timestamp": None,
            "median_interval_seconds": None,
            "minimum_interval_seconds": None,
            "maximum_interval_seconds": None,
            "most_common_interval_seconds": None,
            "note": (
                "Intervals use the current row order. "
                "Check source conventions before interpreting cadence."
            ),
        }

        if len(valid):
            record["first_timestamp"] = serializable(valid.min())
            record["last_timestamp"] = serializable(valid.max())

            differences = valid.diff().dropna()
            record["non_monotonic_count"] = int(
                (differences <= pd.Timedelta(0)).sum()
            )

            positive = differences[
                differences > pd.Timedelta(0)
            ]

            if len(positive):
                seconds = positive.dt.total_seconds()
                record["median_interval_seconds"] = float(seconds.median())
                record["minimum_interval_seconds"] = float(seconds.min())
                record["maximum_interval_seconds"] = float(seconds.max())

                modes = seconds.mode()
                if not modes.empty:
                    record["most_common_interval_seconds"] = float(
                        modes.iloc[0]
                    )

        records.append(record)

    return records


def profile_columns(
    df: pd.DataFrame,
    file_name: str,
    sheet_name: str,
) -> list[dict[str, Any]]:
    records = []
    row_count = len(df)

    for column in df.columns:
        series = df[column]
        non_null = series.dropna()

        examples = [
            serializable(value)
            for value in non_null.head(5).tolist()
        ]

        numeric = pd.to_numeric(series, errors="coerce")
        numeric_valid = numeric.dropna()

        name = str(column).strip().lower()

        records.append({
            "file": file_name,
            "sheet": sheet_name,
            "column": str(column),
            "dtype_as_read": str(series.dtype),
            "rows": row_count,
            "non_missing": int(series.notna().sum()),
            "missing_count": int(series.isna().sum()),
            "missing_fraction": (
                float(series.isna().mean()) if row_count else None
            ),
            "unique_non_missing": int(series.nunique(dropna=True)),
            "numeric_parse_fraction": (
                float(len(numeric_valid) / row_count)
                if row_count else 0.0
            ),
            "numeric_min": (
                float(numeric_valid.min())
                if not numeric_valid.empty else None
            ),
            "numeric_max": (
                float(numeric_valid.max())
                if not numeric_valid.empty else None
            ),
            "likely_physics_variable": any(
                hint in name for hint in PHYSICS_HINTS
            ),
            "sample_values": json.dumps(
                examples, ensure_ascii=False
            ),
        })

    return records


def numeric_summary(
    df: pd.DataFrame,
    file_name: str,
    sheet_name: str,
) -> list[dict[str, Any]]:
    records = []

    for column in df.columns:
        values = pd.to_numeric(df[column], errors="coerce").dropna()

        if values.empty:
            continue

        finite = values[values.map(math.isfinite)]

        records.append({
            "file": file_name,
            "sheet": sheet_name,
            "column": str(column),
            "count": int(len(values)),
            "finite_count": int(len(finite)),
            "mean": float(finite.mean()) if len(finite) else None,
            "std": (
                float(finite.std()) if len(finite) > 1 else None
            ),
            "min": float(finite.min()) if len(finite) else None,
            "q25": (
                float(finite.quantile(0.25)) if len(finite) else None
            ),
            "median": (
                float(finite.median()) if len(finite) else None
            ),
            "q75": (
                float(finite.quantile(0.75)) if len(finite) else None
            ),
            "max": float(finite.max()) if len(finite) else None,
            "zero_count": int((finite == 0).sum()),
            "negative_count": int((finite < 0).sum()),
            "non_finite_count": int((~values.map(math.isfinite)).sum()),
        })

    return records


def inspect_sheet(
    df: pd.DataFrame,
    path: Path,
    sheet_name: str,
):
    df = df.copy()
    df.columns = [clean_name(column) for column in df.columns]

    empty_rows = int(df.isna().all(axis=1).sum())
    empty_columns = int(df.isna().all(axis=0).sum())

    usable = df.loc[~df.isna().all(axis=1)].copy()
    duplicate_rows = int(usable.duplicated().sum())

    inventory = {
        "file": path.name,
        "sheet": sheet_name,
        "extension": path.suffix.lower(),
        "rows_including_blank_rows": len(df),
        "columns": len(df.columns),
        "completely_empty_rows": empty_rows,
        "completely_empty_columns": empty_columns,
        "duplicate_rows": duplicate_rows,
        "duplicate_fraction": (
            duplicate_rows / len(usable) if len(usable) else None
        ),
        "columns_list": json.dumps(
            [str(column) for column in df.columns],
            ensure_ascii=False,
        ),
        "likely_pyroelectric_data": any(
            hint in str(column).lower()
            for column in df.columns
            for hint in PHYSICS_HINTS
        ),
    }

    profile = profile_columns(usable, path.name, sheet_name)
    summary = numeric_summary(usable, path.name, sheet_name)
    timestamps = audit_timestamps(usable, path.name, sheet_name)

    preview = usable.head(15).copy()
    preview.insert(0, "__source_file", path.name)
    preview.insert(1, "__source_sheet", sheet_name)

    return inventory, profile, summary, timestamps, preview


def inspect_raw_preview(
    path: Path,
    sheet_name: str | None = None,
) -> pd.DataFrame:
    """Capture initial rows without assuming the first row is a header."""
    if path.suffix.lower() == ".csv":
        raw = read_raw_csv_preview(path)
    else:
        raw = pd.read_excel(
            path,
            sheet_name=sheet_name,
            header=None,
            nrows=12,
            engine="openpyxl",
        )

    raw.insert(0, "__row_number_1_based", range(1, len(raw) + 1))
    raw.insert(1, "__source_file", path.name)
    raw.insert(2, "__source_sheet", sheet_name or "CSV")
    return raw


def read_raw_csv_preview(path: Path) -> pd.DataFrame:
    errors = []

    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return pd.read_csv(
                path,
                sep=None,
                engine="python",
                header=None,
                nrows=12,
                encoding=encoding,
                on_bad_lines="warn",
            )
        except (
            UnicodeDecodeError,
            pd.errors.ParserError,
            ValueError,
            OSError,
        ) as exc:
            errors.append(f"{encoding}: {exc}")

    raise RuntimeError(
        "Could not read raw CSV preview:\n" + "\n".join(errors)
    )


def audit_folder(folder: Path) -> None:
    if not folder.exists() or not folder.is_dir():
        raise NotADirectoryError(f"Folder does not exist: {folder}")

    files = sorted(
        path for path in folder.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not path.name.startswith(OUTPUT_PREFIX)
        and not path.name.startswith("~$")
        and path.name != Path(__file__).name
    )

    if not files:
        print(f"No CSV or Excel files found in: {folder}")
        return

    file_records = []
    inventory_records = []
    profile_records = []
    numeric_records = []
    timestamp_records = []
    previews = []
    error_records = []

    print("\nREGAIN DATA AUDIT")
    print(f"Folder: {folder}")
    print(f"Files found: {len(files)}\n")

    for path in files:
        print(f"Inspecting: {path.name}")

        try:
            if path.suffix.lower() == ".csv":
                sheets = [None]
            else:
                sheets = pd.ExcelFile(
                    path, engine="openpyxl"
                ).sheet_names

            file_records.append({
                "file": path.name,
                "relative_path": str(path.relative_to(folder)),
                "size_bytes": path.stat().st_size,
                "extension": path.suffix.lower(),
                "sheets": json.dumps(sheets),
                "status": "readable",
                "error": "",
            })

            for sheet in sheets:
                df = load_table(path, sheet)
                sheet_label = sheet or "CSV"

                inventory, profile, summary, timestamps, preview = (
                    inspect_sheet(df, path, sheet_label)
                )

                inventory_records.append(inventory)
                profile_records.extend(profile)
                numeric_records.extend(summary)
                timestamp_records.extend(timestamps)
                previews.append(preview)

                raw_preview = inspect_raw_preview(path, sheet)
                raw_preview.columns = [
                    f"RAW_{column}" for column in raw_preview.columns
                ]
                previews.append(raw_preview)

                print(
                    f"  {sheet_label}: "
                    f"{len(df)} rows x {len(df.columns)} columns"
                )

        except Exception as exc:
            message = repr(exc)

            error_records.append({
                "file": path.name,
                "error": message,
            })

            file_records.append({
                "file": path.name,
                "relative_path": str(path.relative_to(folder)),
                "size_bytes": path.stat().st_size,
                "extension": path.suffix.lower(),
                "sheets": "",
                "status": "error",
                "error": message,
            })

            print(f"  ERROR: {message}")

    file_df = pd.DataFrame(file_records)
    inventory_df = pd.DataFrame(inventory_records)
    profile_df = pd.DataFrame(profile_records)
    numeric_df = pd.DataFrame(numeric_records)
    timestamp_df = pd.DataFrame(timestamp_records)
    errors_df = pd.DataFrame(error_records)

    preview_df = (
        pd.concat(previews, ignore_index=True, sort=False)
        if previews else pd.DataFrame()
    )

    file_df.to_csv(folder / "REGAIN_file_inventory.csv", index=False)
    profile_df.to_csv(folder / "REGAIN_column_profile.csv", index=False)
    numeric_df.to_csv(folder / "REGAIN_numeric_summary.csv", index=False)
    timestamp_df.to_csv(
        folder / "REGAIN_timestamp_diagnostics.csv", index=False
    )

    report_path = folder / "REGAIN_data_audit.xlsx"

    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        sheets = {
            "File Inventory": file_df,
            "Sheet Summary": inventory_df,
            "Column Profile": profile_df,
            "Numeric Summary": numeric_df,
            "Timestamp Checks": timestamp_df,
            "Data Previews": preview_df,
            "Read Errors": errors_df,
        }

        for sheet_name, data in sheets.items():
            data.to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
            )

        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions

            for cells in worksheet.columns:
                values = [
                    len(str(cell.value))
                    for cell in list(cells)[:200]
                    if cell.value is not None
                ]
                width = min(max(max(values, default=10) + 2, 10), 48)
                worksheet.column_dimensions[
                    cells[0].column_letter
                ].width = width

    print("\nAUDIT COMPLETE")
    print(f"Workbook: {report_path}")
    print(f"Inventory: {folder / 'REGAIN_file_inventory.csv'}")
    print(f"Columns: {folder / 'REGAIN_column_profile.csv'}")
    print(f"Numeric summary: {folder / 'REGAIN_numeric_summary.csv'}")
    print(f"Timestamp checks: {folder / 'REGAIN_timestamp_diagnostics.csv'}")

    if error_records:
        print(
            f"\nWARNING: {len(error_records)} file(s) could not be read. "
            "Check the 'Read Errors' worksheet."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit pyroelectric experimental data files."
    )
    parser.add_argument(
        "--folder",
        type=Path,
        default=Path.cwd(),
        help="Folder containing CSV and Excel source data.",
    )
    args = parser.parse_args()

    try:
        audit_folder(args.folder.expanduser().resolve())
        return 0
    except Exception as exc:
        print(f"FATAL ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    warnings.filterwarnings("default", category=UserWarning)
    raise SystemExit(main())
