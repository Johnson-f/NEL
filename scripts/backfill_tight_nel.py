#!/usr/bin/env python3
"""Build Tight NEL files for existing dated NEL snapshots."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from focus_list import prepare_for_export  # noqa: E402
from industry_flow_dashboard import write_dashboard  # noqa: E402
from tight_nel import fetch_histories, find_tight_nel  # noqa: E402


def main() -> int:
    output_dir = PROJECT_DIR / "outputs"
    snapshots: list[tuple[date, pd.DataFrame]] = []
    symbols: set[str] = set()
    for path in sorted(output_dir.glob("non_extended_leaders_*.csv")):
        match = re.search(r"(\d{4}-\d{2}-\d{2})\.csv$", path.name)
        if not match:
            continue
        frame = pd.read_csv(path)
        snapshot_date = date.fromisoformat(match.group(1))
        snapshots.append((snapshot_date, frame))
        symbols.update(frame["name"].dropna().astype(str))

    histories, errors = fetch_histories(symbols)
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(exist_ok=True)
    for snapshot_date, nel in snapshots:
        # Snapshot labels represent the next session, so only use bars that
        # closed strictly before the label date.
        dated_histories = {
            symbol: history.loc[pd.to_datetime(history["date"], utc=True).dt.date < snapshot_date].copy()
            for symbol, history in histories.items()
        }
        tight, _ = find_tight_nel(nel, histories=dated_histories)
        stamp = snapshot_date.isoformat()
        prepare_for_export(tight).to_csv(output_dir / f"tight_non_extended_leaders_{stamp}.csv", index=False)
        tight.loc[:, ["name"]].rename(columns={"name": "symbol"}).to_csv(
            export_dir / f"tight_nel_symbols_{stamp}.csv", index=False
        )
        print(f"{stamp}: {len(tight)} Tight NEL")

    write_dashboard(output_dir)
    if errors:
        print(f"Warning: no price history for {len(errors)} symbol(s): {', '.join(sorted(errors))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
