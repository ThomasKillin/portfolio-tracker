import os
from datetime import datetime, timedelta
from typing import List, Optional

import requests
from dotenv import load_dotenv

import yfinance as yf

try:
    import finnhub  # type: ignore
except ImportError:
    finnhub = None


load_dotenv()


def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def test_yfinance(tickers_au: List[str], tickers_us: List[str]) -> None:
    print_section("Testing yfinance (Yahoo Finance, no API key required)")

    def _check_ticker(ticker: str) -> None:
        print(f"\nTicker: {ticker}")
        try:
            start = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
            df = yf.Ticker(ticker).history(start=start, auto_adjust=False).tz_localize(
                None
            )
            if df.empty:
                print("Status: FAILED - No data returned")
                print(
                    "Possible causes: symbol not supported by Yahoo, delisted, or regional/FX pair limitations."
                )
            else:
                print("Status: OK")
                print(f"Rows returned: {len(df)}")
                print(f"Date range: {df.index.min().date()} -> {df.index.max().date()}")
        except Exception as e:
            print("Status: ERROR during request")
            print(f"Exception type: {type(e).__name__}")
            print(f"Details: {e}")

    print("\n--- Australian tickers via yfinance ---")
    for t in tickers_au:
        _check_ticker(t)

    print("\n--- US tickers via yfinance ---")
    for t in tickers_us:
        _check_ticker(t)


def test_finnhub(tickers_au: List[str], tickers_us: List[str]) -> None:
    print_section("Testing Finnhub API")

    api_key = os.getenv("FINNHUB_API_KEY")
    if finnhub is None:
        print("Status: SKIPPED - 'finnhub' package is not installed.")
        return

    if not api_key:
        print("Status: SKIPPED - FINNHUB_API_KEY not found in environment/.env")
        return

    client = finnhub.Client(api_key=api_key)

    def _check_ticker(ticker: str) -> None:
        print(f"\nTicker: {ticker}")
        try:
            end = int(datetime.utcnow().timestamp())
            start = int((datetime.utcnow() - timedelta(days=30)).timestamp())
            data = client.stock_candles(ticker, "D", start, end)

            status = data.get("s")
            if status == "ok":
                closes = data.get("c", [])
                times = data.get("t", [])
                print("Status: OK")
                print(f"Rows returned: {len(closes)}")
                if times:
                    first = datetime.utcfromtimestamp(times[0]).date()
                    last = datetime.utcfromtimestamp(times[-1]).date()
                    print(f"Date range: {first} -> {last}")
            elif status == "no_data":
                print("Status: FAILED - Finnhub returned 'no_data'")
                print(
                    "Possible causes: symbol not supported on your plan, incorrect symbol, "
                    "or exchange not covered."
                )
            else:
                print(f"Status: FAILED - Finnhub status '{status}'")
        except finnhub.FinnhubAPIException as e:  # type: ignore[attr-defined]
            print("Status: ERROR - FinnhubAPIException")
            print(f"HTTP status code: {getattr(e, 'status_code', 'unknown')}")
            print(f"Details: {e}")
            if getattr(e, "status_code", None) in (401, 403):
                print(
                    "Likely cause: API key invalid, missing permissions, or plan "
                    "does not include this exchange/instrument."
                )
        except Exception as e:
            print("Status: ERROR during request")
            print(f"Exception type: {type(e).__name__}")
            print(f"Details: {e}")

    print("\n--- Australian tickers via Finnhub ---")
    for t in tickers_au:
        _check_ticker(t)

    print("\n--- US tickers via Finnhub ---")
    for t in tickers_us:
        _check_ticker(t)


def alpha_vantage_request(
    symbol: str, api_key: str, function: str = "TIME_SERIES_DAILY_ADJUSTED"
) -> Optional[dict]:
    url = "https://www.alphavantage.co/query"
    params = {
        "function": function,
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": api_key,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def test_alpha_vantage(tickers_au: List[str], tickers_us: List[str]) -> None:
    print_section("Testing Alpha Vantage API")

    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        print("Status: SKIPPED - ALPHA_VANTAGE_API_KEY not found in environment/.env")
        return

    def _interpret_response(symbol: str, data: dict) -> None:
        keys = list(data.keys())
        if "Error Message" in data:
            print("Status: FAILED - Error Message in response")
            print(f"Error Message: {data['Error Message']}")
            print(
                "Likely cause: invalid symbol, unsupported exchange, or incorrect function."
            )
            return

        if "Note" in data:
            print("Status: FAILED - Rate limit / usage note in response")
            print(f"Note: {data['Note']}")
            print(
                "Likely cause: free-tier rate limit hit (per-minute or per-day). "
                "Try reducing request frequency or using a premium key."
            )
            return

        if "Information" in data and "Time Series (Daily)" not in data:
            print("Status: FAILED - Only 'Information' field present")
            print(f"Information: {data['Information']}")
            print(
                "Likely cause: usage/rate-limiting or feature limitation on the free plan."
            )
            return

        ts = data.get("Time Series (Daily)")
        if not ts:
            print("Status: FAILED - No 'Time Series (Daily)' in response")
            print(f"Available keys: {keys}")
            print(
                "Likely cause: symbol/exchange not supported by this endpoint, "
                "or response truncated due to plan limitations."
            )
            return

        # We have time series data
        print("Status: OK")
        print(f"Number of daily points: {len(ts)}")
        dates = sorted(ts.keys())
        if dates:
            print(f"Date range: {dates[0]} -> {dates[-1]}")

    def _check_ticker(ticker: str) -> None:
        print(f"\nTicker: {ticker}")
        try:
            data = alpha_vantage_request(ticker, api_key)
            if data is None:
                print("Status: FAILED - No data returned (None)")
            else:
                _interpret_response(ticker, data)
        except requests.exceptions.HTTPError as e:
            print("Status: ERROR - HTTP error from Alpha Vantage")
            print(f"HTTP status code: {e.response.status_code if e.response else 'unknown'}")
            print(f"Details: {e}")
        except requests.exceptions.RequestException as e:
            print("Status: ERROR - Network/connection error")
            print(f"Exception type: {type(e).__name__}")
            print(f"Details: {e}")
        except Exception as e:
            print("Status: ERROR during request")
            print(f"Exception type: {type(e).__name__}")
            print(f"Details: {e}")

    print("\n--- Australian tickers via Alpha Vantage ---")
    for t in tickers_au:
        _check_ticker(t)

    print("\n--- US tickers via Alpha Vantage ---")
    for t in tickers_us:
        _check_ticker(t)


def test_stooq_free(tickers_au: List[str], tickers_us: List[str]) -> None:
    """
    Stooq provides free CSV downloads for many markets (no API key required).
    This is a lightweight sanity check for ASX/US coverage outside of the main providers.
    """
    print_section("Testing Stooq (free CSV, no API key)")

    def _stooq_symbol(ticker: str) -> str:
        # For many ASX tickers, pattern is e.g. BHP.AU, CBA.AU; for US, AAPL.US
        if ticker.endswith(".AX"):
            base = ticker.replace(".AX", "")
            return f"{base}.AU"
        else:
            return f"{ticker}.US"

    def _check_ticker(ticker: str, region: str) -> None:
        s = _stooq_symbol(ticker)
        print(f"\nTicker: {ticker} (Stooq symbol: {s}, region: {region})")
        url = f"https://stooq.com/q/d/l/?s={s}&i=d"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                print("Status: FAILED - HTTP error")
                print(f"HTTP status code: {resp.status_code}")
                return

            text = resp.text.strip()
            if not text:
                print("Status: FAILED - Empty response body")
                return

            lines = text.splitlines()
            if len(lines) <= 1:
                print(
                    "Status: FAILED - Only header or no data rows returned (symbol may not be supported)."
                )
                return

            print("Status: OK")
            print(f"Rows returned (including header): {len(lines)}")
            print("First data row:", lines[1])
        except Exception as e:
            print("Status: ERROR during request")
            print(f"Exception type: {type(e).__name__}")
            print(f"Details: {e}")

    print("\n--- Australian tickers via Stooq ---")
    for t in tickers_au:
        _check_ticker(t, region="AU")

    print("\n--- US tickers via Stooq ---")
    for t in tickers_us:
        _check_ticker(t, region="US")


def main() -> None:
    # You can adjust this list if you want to test different symbols.
    tickers_au = ["QBE.AX", "BHP.AX", "STW.AX"]
    tickers_us = ["AAPL", "NVDA", "SPY"]

    test_yfinance(tickers_au, tickers_us)
    test_finnhub(tickers_au, tickers_us)
    test_alpha_vantage(tickers_au, tickers_us)
    test_stooq_free(tickers_au, tickers_us)


if __name__ == "__main__":
    main()

