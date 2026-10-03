"""Add 1-year performance and leader flags to saved stock-scan snapshots.

Stock snapshot filenames intentionally represent the *next* trading session.
For example, ``2026-10-05`` is built from Friday 2026-10-02's close.  This
script preserves each saved TradingView universe and only supplements it with
Yahoo daily history needed for the new 1-year performance window.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from math import ceil
from pathlib import Path
import sys

import pandas as pd
import yfinance as yf

# Allow direct execution from ``scripts/`` while keeping the project's normal
# modules importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from focus_list import Settings, prepare_for_export
from industry_flow_dashboard import write_dashboard
from tight_nel import CoilSettings, find_tight_nel


OUTPUT_PATTERNS = ("filtered_universe_*.csv",)


def yahoo_symbol(symbol: str) -> str:
    return str(symbol).strip().upper().replace(".", "-")


def snapshot_stamps(output_dir: Path) -> list[str]:
    stamps = set()
    for pattern in OUTPUT_PATTERNS:
        for path in output_dir.glob(pattern):
            stamp = path.stem.removeprefix("filtered_universe_")
            try:
                date.fromisoformat(stamp)
            except ValueError:
                continue
            stamps.add(stamp)
    return sorted(stamps)


def close_date_for_snapshot(stamp: str) -> pd.Timestamp:
    """Return the latest available close on/before the day before its label."""
    return pd.Timestamp(date.fromisoformat(stamp) - timedelta(days=1))


def fetch_history(symbols: set[str], start: pd.Timestamp, end: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """Download adjusted daily OHLC history once for the complete saved universe."""
    yahoo_to_original = {yahoo_symbol(symbol): symbol for symbol in sorted(symbols)}
    histories: dict[str, pd.DataFrame] = {}
    yahoo_symbols = list(yahoo_to_original)
    # Yahoo can time out on one very large multi-ticker request. Batches make
    # retries predictable and leave a visible progress trail in Actions/CLI.
    for start_index in range(0, len(yahoo_symbols), 100):
        batch = yahoo_symbols[start_index:start_index + 100]
        print(f"Downloading history {start_index + 1}-{start_index + len(batch)} of {len(yahoo_symbols)}...", flush=True)
        downloaded = yf.download(
            batch,
            start=start.date().isoformat(),
            end=(end + pd.Timedelta(days=1)).date().isoformat(),
            interval="1d",
            auto_adjust=True,
            actions=False,
            group_by="ticker",
            threads=True,
            progress=False,
            timeout=20,
        )
        for yahoo in batch:
            original = yahoo_to_original[yahoo]
            try:
                if isinstance(downloaded.columns, pd.MultiIndex):
                    frame = downloaded[yahoo]
                else:
                    frame = downloaded
                frame = frame.rename(columns=str.lower).loc[:, ["high", "low", "close"]].dropna()
                frame.index = pd.to_datetime(frame.index).tz_localize(None)
                if not frame.empty:
                    histories[original] = frame.sort_index()
            except (KeyError, TypeError):
                continue
    return histories


def value_on_or_before(history: pd.DataFrame, when: pd.Timestamp) -> float | None:
    values = history.loc[history.index <= when, "close"]
    if values.empty:
        return None
    value = float(values.iloc[-1])
    return value if value > 0 else None


def perf_one_year(history: pd.DataFrame, close_date: pd.Timestamp) -> float | None:
    recent = value_on_or_before(history, close_date)
    prior = value_on_or_before(history, close_date - pd.DateOffset(years=1))
    # TradingView's Perf.Y follows a new listing from its first available close
    # until it has a complete year of history. Mirror that convention instead
    # of dropping IPOs from the otherwise unchanged historical scan universe.
    if prior is None:
        available = history.loc[history.index <= close_date, "close"]
        prior = float(available.iloc[0]) if not available.empty else None
    if recent is None or prior is None:
        return None
    return 100 * (recent / prior - 1)


def settings_for_stamp(output_dir: Path, stamp: str) -> Settings:
    path = output_dir / f"settings_{stamp}.csv"
    if not path.exists():
        return Settings()
    values = pd.read_csv(path).set_index("setting")["value"].to_dict()
    return Settings(
        min_adr_pct=float(values.get("min_adr_pct", Settings.min_adr_pct)),
        top_pct=float(values.get("top_pct", Settings.top_pct)),
        max_atr_extension=float(values.get("max_atr_extension", Settings.max_atr_extension)),
        min_dollar_volume=float(values.get("min_dollar_volume", Settings.min_dollar_volume)),
        min_avg_volume_10d=float(values.get("min_avg_volume_10d", Settings.min_avg_volume_10d)),
    )


def rebuild_snapshot(output_dir: Path, stamp: str, histories: dict[str, pd.DataFrame]) -> tuple[int, int]:
    universe_path = output_dir / f"filtered_universe_{stamp}.csv"
    universe = pd.read_csv(universe_path)
    close_date = close_date_for_snapshot(stamp)
    performance = {
        symbol: perf_one_year(history, close_date)
        for symbol, history in histories.items()
    }
    universe["Perf.Y"] = universe["name"].map(performance)
    missing = universe.loc[universe["Perf.Y"].isna(), "name"].astype(str).tolist()
    if missing:
        raise ValueError(f"{stamp} has no usable price history for: {', '.join(missing[:10])}")

    universe["Perf.Y"] = pd.to_numeric(universe["Perf.Y"], errors="raise")
    settings = settings_for_stamp(output_dir, stamp)
    ordered = universe.sort_values(["Perf.Y", "name"], ascending=[False, True], kind="stable")
    ranks = pd.Series(range(1, len(ordered) + 1), index=ordered.index, dtype="int64")
    universe["perf_1y_rank"] = ranks
    universe["is_top_1y"] = universe["perf_1y_rank"] <= max(1, ceil(len(universe) * settings.top_pct))
    universe["momentum_score"] = universe[["Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y"]].mean(axis=1)

    leader_flags = ["is_top_1m", "is_top_3m", "is_top_6m", "is_top_1y"]
    leaders = universe.loc[universe[leader_flags].fillna(False).astype(bool).any(axis=1)].copy()
    leaders.sort_values(["momentum_score", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y"], ascending=False, inplace=True)
    nel = leaders.loc[pd.to_numeric(leaders["atr_extension_from_50d"], errors="coerce") <= settings.max_atr_extension].copy()

    # Re-run the tightness rules as-of the original close, including stocks
    # newly admitted by the 1-year ranking.
    as_of_histories: dict[str, pd.DataFrame] = {}
    for symbol in nel["name"].astype(str):
        history = histories.get(symbol)
        if history is None:
            continue
        frame = history.loc[history.index <= close_date].copy()
        if not frame.empty:
            frame.insert(0, "date", frame.index)
            as_of_histories[symbol] = frame.reset_index(drop=True)
    tight, _ = find_tight_nel(nel, histories=as_of_histories, settings=CoilSettings())

    for prefix, frame in (
        ("filtered_universe", universe),
        ("momentum_leaders", leaders),
        ("non_extended_leaders", nel),
        ("tight_non_extended_leaders", tight),
    ):
        prepare_for_export(frame).to_csv(output_dir / f"{prefix}_{stamp}.csv", index=False)
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(exist_ok=True)
    nel.loc[:, ["name"]].rename(columns={"name": "symbol"}).to_csv(export_dir / f"nel_symbols_{stamp}.csv", index=False)
    tight.loc[:, ["name"]].rename(columns={"name": "symbol"}).to_csv(export_dir / f"tight_nel_symbols_{stamp}.csv", index=False)
    return len(leaders), 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill 1-year stock leadership into saved snapshots.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--download-batch", type=int, help="Download one zero-based history batch into the local cache.")
    parser.add_argument("--batch-size", type=int, default=50, help="Symbols per resumable download batch (default: 50).")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild saved snapshots from the completed history cache.")
    args = parser.parse_args()
    stamps = snapshot_stamps(args.output_dir)
    if not stamps:
        raise SystemExit("No saved filtered-universe snapshots found.")
    frames = [pd.read_csv(args.output_dir / f"filtered_universe_{stamp}.csv") for stamp in stamps]
    symbols = set(pd.concat(frames, ignore_index=True)["name"].dropna().astype(str))
    earliest_close = close_date_for_snapshot(stamps[0]) - pd.DateOffset(years=1) - pd.Timedelta(days=7)
    latest_close = close_date_for_snapshot(stamps[-1])
    cache_path = args.output_dir / ".stock_history_1y_cache.pkl"
    histories: dict[str, pd.DataFrame] = pd.read_pickle(cache_path) if cache_path.exists() else {}
    ordered_symbols = sorted(symbols)

    if args.download_batch is not None:
        start = args.download_batch * args.batch_size
        batch = set(ordered_symbols[start:start + args.batch_size])
        if not batch:
            raise SystemExit(f"Batch {args.download_batch} is outside the {len(ordered_symbols)}-symbol universe.")
        histories.update(fetch_history(batch, earliest_close, latest_close))
        pd.to_pickle(histories, cache_path)
        print(f"Cached {len(histories)} of {len(ordered_symbols)} symbols after batch {args.download_batch}.")
        return

    if not args.rebuild:
        histories.update(fetch_history(symbols, earliest_close, latest_close))
        pd.to_pickle(histories, cache_path)
    missing_history = sorted(symbols.difference(histories))
    if missing_history:
        raise SystemExit(
            f"History cache is incomplete ({len(histories)} of {len(symbols)} symbols). "
            "Run each --download-batch first; missing: " + ", ".join(missing_history[:10])
        )
    for stamp in stamps:
        leaders, _ = rebuild_snapshot(args.output_dir, stamp, histories)
        print(f"Backfilled {stamp}: {leaders} liquid leaders.")
    print(write_dashboard(args.output_dir))


if __name__ == "__main__":
    main()
