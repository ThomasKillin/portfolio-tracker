import unittest
import warnings
from unittest.mock import patch
import tempfile

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
    def test_get_userdata_drops_blank_and_nan_company_rows(self) -> None:
        csv_text = """Company,Date,Shares,Price
,01/01/2024,10,100
nan,02/01/2024,5,110
AAA,03/01/2024,3,120
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tf:
            tf.write(csv_text)
            path = tf.name
        try:
            user = share.get_userdata(path)
        finally:
            import os
            os.unlink(path)

        companies = set(user.columns.get_level_values("Company"))
        self.assertEqual(companies, {"AAA"})

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

    def test_stock_summary_daily_return_present_when_benchmark_matches_holding(self) -> None:
        portfolio = make_portfolio_base()
        processed = share.process_data(portfolio)
        summary = share.stock_summary(processed, index="AAA", styles=False, calc_method="basic")
        aaa_row = summary[summary["Company"] == "AAA"].iloc[0]
        self.assertNotEqual(float(aaa_row["Current Holdings"]), 0.0)
        self.assertTrue(pd.notna(aaa_row["Daily Return (%)"]))
        self.assertNotEqual(float(aaa_row["Daily Return (%)"]), 0.0)

    def test_process_data_preserves_benchmark_market_columns(self) -> None:
        idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
        cols = pd.MultiIndex.from_tuples(
            [
                ("Shares", "AAA"),
                ("Price", "AAA"),
                ("Div", "AAA"),
                ("$", "AAA"),
                ("$", "IDX"),
                ("Div", "IDX"),
            ],
            names=["Params", "Company"],
        )
        portfolio = pd.DataFrame(
            [
                [10, 100.0, 0.0, 101.0, 200.0, 0.0],
                [0, 0.0, 0.5, 102.0, 202.0, 0.0],
            ],
            index=idx,
            columns=cols,
        )
        processed = share.process_data(portfolio)
        self.assertIn(("$", "IDX"), processed.columns)
        self.assertIn(("Div", "IDX"), processed.columns)

    def test_merge_pricedata_soft_fail_does_not_reuse_previous_ticker_data(self) -> None:
        idx = pd.to_datetime(["2024-01-02"])
        cols = pd.MultiIndex.from_tuples(
            [("Shares", "AAA"), ("Price", "AAA"), ("Div", "AAA")],
            names=["Params", "Company"],
        )
        portfolio = pd.DataFrame([[10, 100.0, 0.0]], index=idx, columns=cols)

        batch = pd.DataFrame(
            {
                ("AAA", "Close"): [101.0, 102.0],
                ("AAA", "Dividends"): [0.0, 0.5],
            },
            index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        )
        batch.columns = pd.MultiIndex.from_tuples(batch.columns)

        with patch.object(share.yf, "download", return_value=batch):
            merged = share.merge_pricedata(portfolio, "IDX")

        self.assertIn(("$", "AAA"), merged.columns)
        self.assertNotIn(("$", "IDX"), merged.columns)
        self.assertIn("price_fetch", merged.attrs)
        self.assertIn("IDX", merged.attrs["price_fetch"]["failed"])

    def test_convert_currency_unknown_currency_leaves_data_unchanged(self) -> None:
        portfolio = make_portfolio_base()

        class BadTicker:
            def get_history_metadata(self):
                raise RuntimeError("no metadata")

            @property
            def fast_info(self):
                raise RuntimeError("no fast_info")

        with patch.object(share.yf, "Ticker", return_value=BadTicker()):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                converted = share.convert_currency(portfolio, target_currency="AUD")

        pd.testing.assert_frame_equal(converted, portfolio)
        self.assertTrue(any("leaving unchanged" in str(w.message) for w in caught))


if __name__ == "__main__":
    unittest.main()
