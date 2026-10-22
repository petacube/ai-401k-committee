"""Price data: download (Yahoo Finance), cache, splice proxies into long monthly sleeve histories.

Files
  data/prices_daily.csv     cache of adjusted daily closes (dividends reinvested), refreshed by `ai401k data`
  data/prices_snapshot.csv  snapshot shipped with the kit, used offline or when Yahoo is unreachable
"""
from __future__ import annotations

import shutil
import warnings

import numpy as np
import pandas as pd

from . import SLEEVES
from .config import DATA, universe

CACHE = DATA / "prices_daily.csv"
SNAPSHOT = DATA / "prices_snapshot.csv"
START = "2000-01-01"


def symbols(uni: dict | None = None) -> list[str]:
    uni = uni or universe()
    out: list[str] = []
    for s in SLEEVES:
        for sym in [uni[s]["ticker"], *uni[s].get("history", [])]:
            sym = sym.split(":", 1)[1] if sym.startswith("yield:") else sym
            if sym not in out:
                out.append(sym)
    return out


def download(syms: list[str]) -> pd.DataFrame:
    import yfinance as yf

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = yf.download(syms, start=START, auto_adjust=True, progress=False, threads=True)
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": syms[0]})
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.sort_index()


def refresh(offline: bool = False) -> tuple[pd.DataFrame, str]:
    """Update the cache. Returns (prices, message). Never leaves you without data if a snapshot exists."""
    DATA.mkdir(parents=True, exist_ok=True)
    if offline:
        shutil.copy(SNAPSHOT, CACHE)
        return load_daily(), f"offline: copied bundled snapshot to {CACHE.name}"
    syms = symbols()
    try:
        px = download(syms)
        missing = [s for s in syms if s not in px.columns or px[s].dropna().empty]
        if missing:
            raise RuntimeError(f"no data for {missing}")
    except Exception as exc:  # network down, Yahoo throttling, bad ticker
        src = CACHE if CACHE.exists() else SNAPSHOT
        if src != CACHE:
            shutil.copy(SNAPSHOT, CACHE)
        return load_daily(), f"DOWNLOAD FAILED ({exc}); using {src.name} instead"
    px.to_csv(CACHE, float_format="%.6f")
    return px, f"downloaded {len(syms)} symbols, {px.index[0]:%Y-%m-%d} .. {px.index[-1]:%Y-%m-%d}"


def load_daily() -> pd.DataFrame:
    src = CACHE if CACHE.exists() else SNAPSHOT
    if not src.exists():
        raise SystemExit("No price data. Run `ai401k data` (or `ai401k data --offline`).")
    return pd.read_csv(src, index_col=0, parse_dates=True).sort_index()


def _complete_months(daily: pd.DataFrame) -> pd.DataFrame:
    """Month-end closes, dropping the current month if it is not finished yet."""
    m = daily.resample("ME").last()
    last = daily.dropna(how="all").index[-1]
    last_bday = pd.offsets.BMonthEnd().rollforward(last)
    if last < last_bday:
        m = m.iloc[:-1]
    return m


def sleeve_returns(daily: pd.DataFrame | None = None, uni: dict | None = None) -> pd.DataFrame:
    """Monthly total returns per sleeve. Preferred symbol first, proxies fill earlier months."""
    daily = load_daily() if daily is None else daily
    uni = uni or universe()
    monthly = _complete_months(daily)
    out = {}
    for s in SLEEVES:
        r = pd.Series(np.nan, index=monthly.index)
        for sym in [uni[s]["ticker"], *uni[s].get("history", [])]:
            if sym.startswith("yield:"):
                y = monthly.get(sym.split(":", 1)[1])
                if y is None:
                    continue
                cand = (y.shift(1) / 100.0 / 12.0)  # last month's annualised T-bill yield earned this month
            else:
                if sym not in monthly:
                    continue
                cand = monthly[sym].pct_change(fill_method=None)
            r = r.combine_first(cand)
        out[s] = r
    return pd.DataFrame(out).dropna(how="all")


def sleeve_index(rets: pd.DataFrame) -> pd.DataFrame:
    """Total-return index (=1 before the first return) used for trend and momentum signals."""
    return (1 + rets.fillna(0)).cumprod().where(rets.notna().cummax())


def latest_prices(daily: pd.DataFrame | None = None, uni: dict | None = None) -> dict:
    """Last close of each trade ticker: {sleeve: {ticker, price, date}}."""
    daily = load_daily() if daily is None else daily
    uni = uni or universe()
    out = {}
    for s in SLEEVES:
        t = uni[s]["ticker"]
        col = daily[t].dropna()
        out[s] = {"ticker": t, "price": float(col.iloc[-1]), "date": col.index[-1].date().isoformat()}
    return out
