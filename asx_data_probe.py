import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

import pandas as pd
import requests
import yfinance as yf


DEFAULT_TICKERS = ["BHP.AX", "CBA.AX", "WES.AX", "STW.AX", "VAS.AX"]
TARGET_YEARS = 20
MIN_DAYS = int(TARGET_YEARS * 252 * 0.9)  # Trading-day tolerance for holidays/listings


@dataclass
class CheckResult:
    source: str
    ticker: str
    status: str
    rows: int
    first_date: Optional[pd.Timestamp]
    last_date: Optional[pd.Timestamp]
    years: float
    meets_20y: bool
    detail: str


def ensure_ax_suffix(ticker: str) -> str:
    t = ticker.strip().upper()
    if not t:
        return t
    return t if t.endswith(".AX") else f"{t}.AX"


def years_between(first_date: Optional[pd.Timestamp], last_date: Optional[pd.Timestamp]) -> float:
    if first_date is None or last_date is None:
        return 0.0
    return (last_date - first_date).days / 365.25


def summarize_df(source: str, ticker: str, df: pd.DataFrame, detail: str = "") -> CheckResult:
    if df is None or df.empty:
        return CheckResult(source, ticker, "FAILED", 0, None, None, 0.0, False, detail or "No rows returned")

    if isinstance(df.index, pd.DatetimeIndex):
        idx = df.index.tz_localize(None) if df.index.tz is not None else df.index
        first_date = idx.min()
        last_date = idx.max()
    else:
        first_date = None
        last_date = None

    years = years_between(first_date, last_date)
    meets = years >= TARGET_YEARS and len(df) >= MIN_DAYS
    status = "OK" if meets else "PARTIAL"

    return CheckResult(
        source=source,
        ticker=ticker,
        status=status,
        rows=len(df),
        first_date=first_date,
        last_date=last_date,
        years=years,
        meets_20y=meets,
        detail=detail,
    )


def check_yfinance_ticker_history(ticker: str) -> CheckResult:
    """
    Uses Ticker.history with explicit daily interval and max period.
    This mirrors how the app already consumes Yahoo data but stresses long-range coverage.
    """
    try:
        df = yf.Ticker(ticker).history(
            period="max",
            interval="1d",
            auto_adjust=False,
            actions=True,
            repair=True,
            prepost=False,
        )
        if isinstance(df.index, pd.DatetimeIndex):
            df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
        return summarize_df("yfinance.Ticker.history", ticker, df)
    except Exception as exc:
        return CheckResult(
            "yfinance.Ticker.history",
            ticker,
            "ERROR",
            0,
            None,
            None,
            0.0,
            False,
            f"{type(exc).__name__}: {exc}",
        )


def check_yfinance_download(ticker: str) -> CheckResult:
    """
    Uses yf.download as a second Yahoo code path.
    Helpful if one method regressed while the other still works.
    """
    try:
        df = yf.download(
            tickers=ticker,
            period="max",
            interval="1d",
            auto_adjust=False,
            actions=False,
            progress=False,
            threads=False,
            timeout=20,
        )
        if isinstance(df.index, pd.DatetimeIndex):
            df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
        return summarize_df("yfinance.download", ticker, df)
    except Exception as exc:
        return CheckResult(
            "yfinance.download",
            ticker,
            "ERROR",
            0,
            None,
            None,
            0.0,
            False,
            f"{type(exc).__name__}: {exc}",
        )


def stooq_symbol_from_ax(ticker: str) -> str:
    return ticker.replace(".AX", "") + ".AU"


def check_stooq_daily_csv(ticker: str) -> CheckResult:
    """
    Lightweight free fallback check from Stooq.
    Not used by app, but useful to verify whether issue is Yahoo-specific.
    """
    symbol = stooq_symbol_from_ax(ticker)
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()

        text = resp.text.strip()
        if not text or text.lower().startswith("no_data"):
            return CheckResult("stooq.csv", ticker, "FAILED", 0, None, None, 0.0, False, "No data body")

        lines = text.splitlines()
        if len(lines) <= 1:
            return CheckResult("stooq.csv", ticker, "FAILED", 0, None, None, 0.0, False, "Header only")

        df = pd.read_csv(pd.io.common.StringIO(text), parse_dates=["Date"])  # type: ignore[arg-type]
        df = df.sort_values("Date")
        idx = pd.DatetimeIndex(df["Date"])
        probe = pd.DataFrame(index=idx)
        detail = f"stooq_symbol={symbol}"
        return summarize_df("stooq.csv", ticker, probe, detail=detail)
    except Exception as exc:
        return CheckResult("stooq.csv", ticker, "ERROR", 0, None, None, 0.0, False, f"{type(exc).__name__}: {exc}")


def format_date(ts: Optional[pd.Timestamp]) -> str:
    return ts.strftime("%Y-%m-%d") if ts is not None else "-"


def print_result(r: CheckResult) -> None:
    print(
        f"[{r.source}] {r.ticker:<9} status={r.status:<7} rows={r.rows:<6} "
        f"range={format_date(r.first_date)} -> {format_date(r.last_date)} "
        f"years={r.years:>5.1f} meets_20y={r.meets_20y}"
    )
    if r.detail:
        print(f"  detail: {r.detail}")


def run_checks(tickers: Iterable[str]) -> int:
    tickers = [ensure_ax_suffix(t) for t in tickers if t.strip()]
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    print("ASX long-history daily data probe")
    print(f"Run time: {now_utc}")
    print(f"Target: >= {TARGET_YEARS} years and >= {MIN_DAYS} daily rows")
    print()

    failures = 0

    for t in tickers:
        print(f"--- {t} ---")
        results = [
            check_yfinance_ticker_history(t),
            check_yfinance_download(t),
            check_stooq_daily_csv(t),
        ]
        for r in results:
            print_result(r)

        yahoo_ok = any(r.source.startswith("yfinance") and r.meets_20y for r in results)
        if not yahoo_ok:
            failures += 1

        print()

    if failures:
        print(f"Summary: {failures}/{len(tickers)} ticker(s) did NOT meet Yahoo 20y daily target.")
        return 1

    print("Summary: all tickers met Yahoo 20y daily target on at least one Yahoo path.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe ASX daily history availability (>20 years) using Yahoo and fallback source checks."
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="ASX tickers (with or without .AX suffix)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_checks(args.tickers)


if __name__ == "__main__":
    sys.exit(main())
