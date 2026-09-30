#!/usr/bin/env python3
"""Persist the completed US after-hours percentage move for the ETF dashboards."""

from __future__ import annotations

import csv
import json
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


def postmarket_changes(symbols: list[str]) -> tuple[str, dict[str, float]]:
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
        return "", {}
    index = pd.DatetimeIndex(prices.index)
    index = index.tz_localize(NY_TZ) if index.tz is None else index.tz_convert(NY_TZ)
    prices = prices.copy()
    prices.index = index
    candidate_dates = sorted({stamp.date() for stamp in index}, reverse=True)
    for session_date in candidate_dates:
        changes: dict[str, float] = {}
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
        if changes:
            return session_date.isoformat(), changes
    return "", {}


def main() -> int:
    now = datetime.now(NY_TZ)
    session_date, changes = postmarket_changes(tickers())
    if not changes:
        raise RuntimeError("Yahoo returned no completed after-hours values; leaving the prior capture intact.")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({"date": session_date, "captured_at": now.isoformat(), "values": changes}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(changes)} completed after-hours values for {session_date}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
