#!/usr/bin/env python3
"""Persist the completed US after-hours percentage move for the ETF dashboards."""

from __future__ import annotations

import csv
import json
import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

try:
    from scripts.run_after_close import NY_TZ
except ModuleNotFoundError:  # Supports direct `python scripts/...` execution.
    from run_after_close import NY_TZ


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_DIR / "outputs" / "etf" / "extended_hours.json"
UNIVERSE_PATHS = (
    PROJECT_DIR / "data" / "theme_etfs.tsv",
    PROJECT_DIR / "data" / "sector_etfs.tsv",
)


def tickers() -> list[str]:
    symbols: set[str] = set()
    for path in UNIVERSE_PATHS:
        with path.open(encoding="utf-8", newline="") as handle:
            symbols.update(row["Ticker"].strip().upper() for row in csv.DictReader(handle, delimiter="\t"))
    return sorted(symbols)


def _ticker_frame(prices: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if not isinstance(prices.columns, pd.MultiIndex):
        return prices
    if symbol not in prices.columns.get_level_values(0):
        return pd.DataFrame()
    return prices[symbol]


def postmarket_changes(symbols: list[str]) -> tuple[str, dict[str, float], dict[str, float], dict[str, float]]:
    """Return the final 4–8 PM move for the latest available session.

    Yahoo's one-minute pre/post-market history retains completed after-hours
    bars for several days, unlike a live scanner field that disappears next
    morning. It is therefore a better source for this persisted value.
    """
    prices = yf.download(
        symbols,
        period="5d",
        interval="1m",
        prepost=True,
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=True,
    )
    if prices.empty:
        return "", {}, {}, {}
    index = pd.DatetimeIndex(prices.index)
    index = index.tz_localize(NY_TZ) if index.tz is None else index.tz_convert(NY_TZ)
    prices = prices.copy()
    prices.index = index
    candidate_dates = sorted({stamp.date() for stamp in index}, reverse=True)
    for session_date in candidate_dates:
        changes: dict[str, float] = {}
        regular_closes: dict[str, float] = {}
        after_hours_closes: dict[str, float] = {}
        for symbol in symbols:
            frame = _ticker_frame(prices, symbol)
            if frame.empty or "Close" not in frame:
                continue
            frame = frame.dropna(subset=["Close"])
            regular = frame[(frame.index.date == session_date) & (frame.index.time >= datetime.strptime("09:30", "%H:%M").time()) & (frame.index.time <= datetime.strptime("16:00", "%H:%M").time())]
            after_hours = frame[(frame.index.date == session_date) & (frame.index.time > datetime.strptime("16:00", "%H:%M").time()) & (frame.index.time < datetime.strptime("20:00", "%H:%M").time())]
            if regular.empty or after_hours.empty:
                continue
            close = float(regular["Close"].iloc[-1])
            after_close = float(after_hours["Close"].iloc[-1])
            if close > 0:
                changes[symbol] = round((after_close / close - 1) * 100, 6)
                regular_closes[symbol] = close
                after_hours_closes[symbol] = after_close
        if changes:
            return session_date.isoformat(), changes, regular_closes, after_hours_closes
    return "", {}, {}, {}


def overnight_changes(symbols: list[str]) -> tuple[str, dict[str, float]]:
    """Return the most recent 8 PM–4 AM session move for each ETF."""
    prices = yf.download(
        symbols,
        period="5d",
        interval="1m",
        prepost=True,
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=True,
    )
    if prices.empty:
        return "", {}
    index = pd.DatetimeIndex(prices.index)
    index = index.tz_localize(NY_TZ) if index.tz is None else index.tz_convert(NY_TZ)
    prices = prices.copy()
    prices.index = index
    session_dates = sorted({stamp.date() for stamp in index}, reverse=True)
    four_am = datetime.strptime("04:00", "%H:%M").time()
    nine_thirty = datetime.strptime("09:30", "%H:%M").time()
    four_pm = datetime.strptime("16:00", "%H:%M").time()
    eight_pm = datetime.strptime("20:00", "%H:%M").time()
    for session_date in session_dates:
        prior_dates = [day for day in session_dates if day < session_date]
        if not prior_dates:
            continue
        prior_date = prior_dates[0]
        changes: dict[str, float] = {}
        for symbol in symbols:
            frame = _ticker_frame(prices, symbol)
            if frame.empty or "Close" not in frame:
                continue
            frame = frame.dropna(subset=["Close"])
            premarket = frame[(frame.index.date == session_date) & (frame.index.time >= four_am) & (frame.index.time < nine_thirty)]
            after_hours = frame[(frame.index.date == prior_date) & (frame.index.time > four_pm) & (frame.index.time < eight_pm)]
            if premarket.empty or after_hours.empty:
                continue
            after_close = float(after_hours["Close"].iloc[-1])
            premarket_open = float(premarket["Close"].iloc[0])
            if after_close > 0:
                changes[symbol] = round((premarket_open / after_close - 1) * 100, 6)
        if changes:
            return session_date.isoformat(), changes
    return "", {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overnight-only", action="store_true", help="Refresh only the retained 8 PM–4 AM session.")
    args = parser.parse_args()
    now = datetime.now(NY_TZ)
    if args.overnight_only:
        overnight_date, overnight = overnight_changes(tickers())
        if not overnight:
            raise RuntimeError("Yahoo returned no completed overnight values; leaving the prior capture intact.")
        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")) if OUTPUT_PATH.exists() else {}
        payload["overnight"] = {"date": overnight_date, "values": overnight}
        payload["captured_at"] = now.isoformat()
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {len(overnight)} completed overnight values for {overnight_date}.")
        return 0
    session_date, changes, regular_closes, after_hours_closes = postmarket_changes(tickers())
    overnight_date, overnight = overnight_changes(tickers())
    if not changes:
        raise RuntimeError("Yahoo returned no completed after-hours values; leaving the prior capture intact.")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({"date": session_date, "captured_at": now.isoformat(), "values": changes, "regular_close": regular_closes, "after_hours_close": after_hours_closes, "overnight": {"date": overnight_date, "values": overnight}}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(changes)} completed after-hours values for {session_date}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
