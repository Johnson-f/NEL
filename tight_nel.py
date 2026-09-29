"""Find fast 3-5 day coils inside the non-extended leader list."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class CoilSettings:
    atr_length: int = 14
    ema_length: int = 9
    coil_length: int = 5
    fast_coil_length: int = 3
    contraction_lookback: int = 10
    max_close_spread_pct: float = 4.0
    max_fast_close_spread_pct: float = 2.5
    max_coil_range_atr: float = 2.5
    max_true_range_ratio: float = 0.85
    max_current_day_range_pct: float = 100.0
    rmv_lookback: int = 15
    rmv_tight_threshold: float = 15.0


TIGHTNESS_COLUMNS = [
    "is_tight_nel",
    "coil_setup",
    "close_above_ema9",
    "close_spread_3d_pct",
    "close_spread_5d_pct",
    "coil_range_5d_atr",
    "true_range_ratio_3d",
    "true_range_ratio_5d",
    "current_day_range_pct_prior_atr",
    "rmv_15d",
    "rmv_tight_days",
]


def _yahoo_symbol(symbol: str) -> str:
    """Translate the small class-share difference used by Yahoo Finance."""
    return symbol.strip().upper().replace(".", "-")


def fetch_histories(symbols: Iterable[str]) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Batch-fetch three months of daily OHLC history with yfinance."""
    unique = sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})
    histories: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    if not unique:
        return histories, errors

    yahoo_to_original = {_yahoo_symbol(symbol): symbol for symbol in unique}
    yahoo_symbols = list(yahoo_to_original)
    try:
        downloaded = yf.download(
            yahoo_symbols,
            period="3mo",
            interval="1d",
            auto_adjust=False,
            actions=False,
            group_by="ticker",
            threads=True,
            progress=False,
            timeout=20,
        )
    except Exception as error:  # yfinance can surface several transport backends
        message = f"yfinance batch download failed: {error}"
        return histories, {symbol: message for symbol in unique}

    for yahoo_symbol, original_symbol in yahoo_to_original.items():
        try:
            if isinstance(downloaded.columns, pd.MultiIndex):
                first_level = set(downloaded.columns.get_level_values(0))
                symbol_frame = downloaded[yahoo_symbol] if yahoo_symbol in first_level else downloaded.xs(yahoo_symbol, axis=1, level=1)
            else:
                symbol_frame = downloaded
            symbol_frame = symbol_frame.rename(columns=str.lower)
            history = symbol_frame.loc[:, ["high", "low", "close"]].dropna().copy()
            history.insert(0, "date", pd.to_datetime(history.index, utc=True))
            if history.empty:
                raise ValueError("no daily OHLC rows returned")
            histories[original_symbol] = history.reset_index(drop=True)
        except (KeyError, TypeError, ValueError) as error:
            errors[original_symbol] = f"Could not parse yfinance history for {original_symbol}: {error}"
    return histories, errors


def _wilder_average(values: pd.Series, period: int) -> pd.Series:
    """Wilder moving average with an SMA seed, matching a standard ATR(14)."""
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    result = pd.Series(float("nan"), index=numeric.index, dtype=float)
    if len(numeric) < period:
        return result
    result.iloc[period - 1] = numeric.iloc[:period].mean()
    for index in range(period, len(numeric)):
        result.iloc[index] = ((period - 1) * result.iloc[index - 1] + numeric.iloc[index]) / period
    return result


def calculate_coil_metrics(history: pd.DataFrame, settings: CoilSettings = CoilSettings()) -> dict | None:
    """Calculate the attached fast-coil rules and an RMV context score."""
    required_bars = max(
        settings.atr_length + 1,
        settings.coil_length + settings.contraction_lookback,
        settings.rmv_lookback + 3,
        settings.ema_length,
    )
    if len(history) < required_bars:
        return None

    frame = history.loc[:, ["high", "low", "close"]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(frame) < required_bars or (frame <= 0).any().any():
        return None

    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = _wilder_average(true_range, settings.atr_length)
    ema = frame["close"].ewm(span=settings.ema_length, adjust=False).mean()
    latest_close = frame["close"].iloc[-1]
    latest_atr = atr.iloc[-1]
    prior_atr = atr.iloc[-2]
    if not pd.notna(latest_atr) or latest_atr <= 0 or not pd.notna(prior_atr) or prior_atr <= 0:
        return None

    close_3 = frame["close"].iloc[-settings.fast_coil_length:]
    close_5 = frame["close"].iloc[-settings.coil_length:]
    spread_3 = 100 * (close_3.max() - close_3.min()) / latest_close
    spread_5 = 100 * (close_5.max() - close_5.min()) / latest_close
    range_5_atr = (
        frame["high"].iloc[-settings.coil_length:].max()
        - frame["low"].iloc[-settings.coil_length:].min()
    ) / latest_atr

    recent_tr_3 = true_range.iloc[-settings.fast_coil_length:].mean()
    prior_tr_3 = true_range.iloc[-(settings.fast_coil_length + settings.contraction_lookback):-settings.fast_coil_length].mean()
    recent_tr_5 = true_range.iloc[-settings.coil_length:].mean()
    prior_tr_5 = true_range.iloc[-(settings.coil_length + settings.contraction_lookback):-settings.coil_length].mean()
    ratio_3 = recent_tr_3 / prior_tr_3 if prior_tr_3 > 0 else float("inf")
    ratio_5 = recent_tr_5 / prior_tr_5 if prior_tr_5 > 0 else float("inf")
    current_range_pct = 100 * (frame["high"].iloc[-1] - frame["low"].iloc[-1]) / prior_atr

    bar_range = frame["high"] - frame["low"]
    prior_max = bar_range.rolling(settings.rmv_lookback).max().shift(1)
    prior_min = bar_range.rolling(settings.rmv_lookback).min().shift(1)
    denominator = (prior_max - prior_min).where((prior_max - prior_min) != 0, 0.000001)
    rmv = (100 * (bar_range - prior_min) / denominator).clip(lower=0, upper=100)
    tight_rmv = rmv < settings.rmv_tight_threshold
    tight_days = 0
    for value in reversed(tight_rmv.fillna(False).tolist()):
        if not value:
            break
        tight_days += 1

    three_day = spread_3 <= settings.max_fast_close_spread_pct and ratio_3 <= settings.max_true_range_ratio
    five_day = spread_5 <= settings.max_close_spread_pct and ratio_5 <= settings.max_true_range_ratio
    common = (
        latest_close > ema.iloc[-1]
        and range_5_atr <= settings.max_coil_range_atr
        and current_range_pct < settings.max_current_day_range_pct
    )
    setup = "3D + 5D" if three_day and five_day else "3D" if three_day else "5D" if five_day else ""
    return {
        "is_tight_nel": bool(common and (three_day or five_day)),
        "coil_setup": setup,
        "close_above_ema9": bool(latest_close > ema.iloc[-1]),
        "close_spread_3d_pct": float(spread_3),
        "close_spread_5d_pct": float(spread_5),
        "coil_range_5d_atr": float(range_5_atr),
        "true_range_ratio_3d": float(ratio_3),
        "true_range_ratio_5d": float(ratio_5),
        "current_day_range_pct_prior_atr": float(current_range_pct),
        "rmv_15d": float(rmv.iloc[-1]) if pd.notna(rmv.iloc[-1]) else float("nan"),
        "rmv_tight_days": int(tight_days),
    }


def find_tight_nel(
    nel: pd.DataFrame,
    histories: dict[str, pd.DataFrame] | None = None,
    settings: CoilSettings = CoilSettings(),
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Return NEL rows passing the fast coil, enriched with tightness metrics."""
    if nel.empty:
        empty = nel.copy()
        for column in TIGHTNESS_COLUMNS:
            empty[column] = pd.Series(dtype="object")
        return empty, {}

    errors: dict[str, str] = {}
    if histories is None:
        histories, errors = fetch_histories(nel["name"])

    metric_rows = []
    for symbol in nel["name"].astype(str):
        history = histories.get(symbol.upper())
        if history is None:
            continue
        metrics = calculate_coil_metrics(history, settings)
        if metrics is not None:
            metric_rows.append({"name": symbol, **metrics})
    if not metric_rows:
        empty = nel.iloc[0:0].copy()
        for column in TIGHTNESS_COLUMNS:
            empty[column] = pd.Series(dtype="object")
        return empty, errors

    metrics_frame = pd.DataFrame(metric_rows)
    enriched = nel.merge(metrics_frame, on="name", how="inner")
    tight = enriched.loc[enriched["is_tight_nel"]].copy()
    tight.sort_values(
        ["rmv_15d", "coil_range_5d_atr", "momentum_score"],
        ascending=[True, True, False],
        inplace=True,
        na_position="last",
    )
    return tight, errors
