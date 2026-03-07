import inspect
import unittest

import numpy as np
import pandas as pd

import performance_calcs as calc


class PerformanceCalcRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.idx = pd.date_range("2024-01-01", periods=6, freq="B")

    def test_dollar_weighted_return_all_zero_does_not_crash(self) -> None:
        val = pd.DataFrame({"A": [0, 0, 0, 0, 0, 0]}, index=self.idx)
        cash_flows = pd.DataFrame({"A": [0, 0, 0, 0, 0, 0]}, index=self.idx)

        result = calc.dollar_weighted_return(val, cash_flows)
        self.assertTrue((result["A"] == 0).all())

    def test_dollar_weighted_total_return_all_zero_does_not_crash(self) -> None:
        val = pd.DataFrame({"A": [0, 0, 0, 0, 0, 0]}, index=self.idx)
        cash_flows = pd.DataFrame({"A": [0, 0, 0, 0, 0, 0]}, index=self.idx)
        div = pd.DataFrame({"A": [0, 0, 0, 0, 0, 0]}, index=self.idx)

        result = calc.dollar_weighted_total_return(val, cash_flows, div)
        self.assertTrue((result["A"] == 0).all())

    def test_dollar_weighted_return_unnamed_index_no_date_key_error(self) -> None:
        idx = pd.DatetimeIndex(self.idx.values)  # unnamed datetime index
        val = pd.DataFrame({"A": [100, 105, 110, 115, 120, 125]}, index=idx)
        cash_flows = pd.DataFrame({"A": [100, 0, 0, 0, 0, 0]}, index=idx)

        result = calc.dollar_weighted_return(val, cash_flows)
        self.assertFalse(result.empty)
        self.assertTrue(result.index.equals(idx))

    def test_time_weighted_annualised_respects_use_initial_cf(self) -> None:
        val = pd.DataFrame({"A": [100, 110, 120, 130, 140, 150]}, index=self.idx)
        cash_flows = pd.DataFrame({"A": [10, 0, 0, 0, 0, 0]}, index=self.idx)
        div = pd.DataFrame({"A": [0, 1, 1, 1, 1, 1]}, index=self.idx)

        twr_false = calc.time_weighted_return_annualised(val, cash_flows, use_initial_CF=False)
        twr_true = calc.time_weighted_return_annualised(val, cash_flows, use_initial_CF=True)
        self.assertFalse(twr_false.equals(twr_true))

        twr_tot_false = calc.time_weighted_total_return_annualised(
            val, cash_flows, div, use_initial_CF=False
        )
        twr_tot_true = calc.time_weighted_total_return_annualised(
            val, cash_flows, div, use_initial_CF=True
        )
        self.assertFalse(twr_tot_false.equals(twr_tot_true))

    def test_daily_portfolio_pct_gain_zero_denominator_returns_zero(self) -> None:
        val = pd.DataFrame({"A": [0, 0, 0, 0, 0, 0]}, index=self.idx)
        price = pd.DataFrame({"A": [10, 11, 12, 13, 14, 15]}, index=self.idx)

        gain = calc.daily_portfolio_pct_gain(val, price)
        self.assertTrue((gain.fillna(0) == 0).all())

    def test_dollar_weighted_return_series_input_graph_path(self) -> None:
        # Graph functions pass Series via val.sum(axis=1), cash_flows.sum(axis=1)
        val = pd.Series([100, 110, 120, 130, 140, 150], index=self.idx, name="portfolio")
        cash_flows = pd.Series([100, 0, 0, 0, 0, 0], index=self.idx, name="portfolio")

        result = calc.dollar_weighted_return(val, cash_flows)
        self.assertFalse(result.empty)

    def test_annualised_returns_are_finite_at_first_non_zero_period(self) -> None:
        val = pd.DataFrame({"A": [100, 120, 130, 140, 150, 160]}, index=self.idx)
        cash_flows = pd.DataFrame({"A": [100, 0, 0, 0, 0, 0]}, index=self.idx)

        basic_ann = calc.basic_return_annualised(val, cash_flows, use_initial_CF=True)
        self.assertTrue(np.isfinite(basic_ann["A"]).all())

    def test_dollar_weighted_return_has_single_resample_step(self) -> None:
        src = inspect.getsource(calc.dollar_weighted_return)
        self.assertEqual(src.count("irr_series = irr_series.resample"), 1)
        self.assertEqual(src.count("vcol_ = vcol.resample"), 1)

    def test_dollar_weighted_return_accepts_weekly_frequency(self) -> None:
        idx = pd.date_range("2024-01-01", periods=520, freq="B")
        val = pd.Series(np.linspace(100.0, 160.0, len(idx)), index=idx, name="portfolio")
        cash_flows = pd.Series(0.0, index=idx, name="portfolio")
        cash_flows.iloc[0] = 100.0

        result = calc.dollar_weighted_return(val, cash_flows, resample_freq="W")
        self.assertFalse(result.empty)

    def test_dollar_weighted_total_return_accepts_weekly_frequency(self) -> None:
        idx = pd.date_range("2024-01-01", periods=520, freq="B")
        val = pd.Series(np.linspace(100.0, 160.0, len(idx)), index=idx, name="portfolio")
        cash_flows = pd.Series(0.0, index=idx, name="portfolio")
        cash_flows.iloc[0] = 100.0
        div = pd.Series(0.0, index=idx, name="portfolio")

        result = calc.dollar_weighted_total_return(
            val, cash_flows, div, resample_freq="W"
        )
        self.assertFalse(result.empty)

    def test_dollar_weighted_endpoint_matches_full_last_value(self) -> None:
        idx = pd.date_range("2024-01-01", periods=260, freq="B")
        val = pd.DataFrame({"A": np.linspace(100.0, 180.0, len(idx))}, index=idx)
        cash_flows = pd.DataFrame({"A": np.zeros(len(idx))}, index=idx)
        cash_flows.iloc[0, 0] = 100.0

        full = calc.dollar_weighted_return(val, cash_flows, resample_freq="M")
        endpoint = calc.dollar_weighted_return_endpoint(val, cash_flows, resample_freq="M")
        self.assertAlmostEqual(float(full.iloc[-1, 0]), float(endpoint["A"]), places=10)

    def test_auto_resample_considers_dataframe_width(self) -> None:
        idx = pd.date_range("2024-01-01", periods=50, freq="B")
        wide = pd.DataFrame(
            np.ones((len(idx), 10)),
            index=idx,
            columns=[f"S{i}" for i in range(10)],
        )
        self.assertEqual(calc._resolve_dwr_resample_freq(wide, "auto", base_rows=100), "W-FRI")


if __name__ == "__main__":
    unittest.main()
