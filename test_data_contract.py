import unittest
import warnings
from unittest.mock import patch

import pandas as pd

import share_tracking as share


def make_portfolio_base() -> pd.DataFrame:
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    cols = pd.MultiIndex.from_tuples(
        [("Shares", "AAA"), ("Price", "AAA"), ("Div", "AAA"), ("$", "AAA")],
        names=["Params", "Company"],
    )
    return pd.DataFrame(
        [
            [10, 100.0, 0.0, 101.0],
            [0, 0.0, 0.5, 102.0],
        ],
        index=idx,
        columns=cols,
    )


class ShareTrackingContractTests(unittest.TestCase):
    def test_process_data_raises_if_price_columns_missing(self) -> None:
        idx = pd.to_datetime(["2024-01-02"])
        cols = pd.MultiIndex.from_tuples(
            [("Shares", "AAA"), ("Price", "AAA"), ("Div", "AAA")],
            names=["Params", "Company"],
        )
        portfolio = pd.DataFrame([[10, 100.0, 0.0]], index=idx, columns=cols)

        with self.assertRaises(ValueError) as ctx:
            share.process_data(portfolio)

        self.assertIn("missing required data columns", str(ctx.exception))
        self.assertIn("$", str(ctx.exception))

    def test_process_data_no_adjustments_keeps_div_defined(self) -> None:
        portfolio = make_portfolio_base()
        processed = share.process_data(portfolio)

        self.assertIn(("Div", "AAA"), processed.columns)
        self.assertIn(("Div_tot", "AAA"), processed.columns)
        self.assertIn(("Val", "AAA"), processed.columns)

    def test_merge_pricedata_soft_fail_does_not_reuse_previous_ticker_data(self) -> None:
        idx = pd.to_datetime(["2024-01-02"])
        cols = pd.MultiIndex.from_tuples(
            [("Shares", "AAA"), ("Price", "AAA"), ("Div", "AAA")],
            names=["Params", "Company"],
        )
        portfolio = pd.DataFrame([[10, 100.0, 0.0]], index=idx, columns=cols)

        class FakeTicker:
            def __init__(self, symbol: str) -> None:
                self.symbol = symbol

            def history(self, start=None, auto_adjust=False):  # noqa: ARG002
                if self.symbol == "AAA":
                    return pd.DataFrame(
                        {
                            "Close": [101.0, 102.0],
                            "Dividends": [0.0, 0.5],
                        },
                        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
                    )
                raise RuntimeError("fetch failed")

        with patch.object(share.yf, "Ticker", side_effect=lambda s: FakeTicker(s)):
            merged = share.merge_pricedata(portfolio, "IDX")

        self.assertIn(("$", "AAA"), merged.columns)
        self.assertNotIn(("$", "IDX"), merged.columns)
        self.assertIn("price_fetch", merged.attrs)
        self.assertIn("IDX", merged.attrs["price_fetch"]["failed"])

    def test_convert_currency_unknown_currency_leaves_data_unchanged(self) -> None:
        portfolio = make_portfolio_base()

        class BadTicker:
            @property
            def history_metadata(self):
                raise RuntimeError("no metadata")

        with patch.object(share.yf, "Ticker", return_value=BadTicker()):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                converted = share.convert_currency(portfolio, target_currency="AUD")

        pd.testing.assert_frame_equal(converted, portfolio)
        self.assertTrue(any("leaving unchanged" in str(w.message) for w in caught))


if __name__ == "__main__":
    unittest.main()
