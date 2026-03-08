import performance_calcs as calc
import pandas as pd
import numpy as np
import seaborn as sns
import warnings

# from datetime import datetime
import sys
import yfinance as yf

# TODO:
# Allow specification of a subset of dates when plotting portfolio performance
# calc_stockdata - change time(t) to be days, not business days
# stock_summary - check whether supplied date argument is a business day
# Dividend metrics
# csv file columns case insensitive
# allow for multiple sales or purcahses in a single day
# Add first purchase date in stock_summary()
# Print time period when displaying summary table and summary plots
# total return - last value before all shares sold
# Date to US format
# fix graph legend if single stock holding
# add support for multiple currencies
# add dividends
# Add automatic control of stock splits


def _extract_ticker_history(download_df, ticker, single_ticker=False):
    """
    Normalize yfinance.download output to a per-ticker DataFrame.
    """
    if download_df is None or download_df.empty:
        return pd.DataFrame()

    if single_ticker:
        return download_df

    if isinstance(download_df.columns, pd.MultiIndex):
        if ticker in download_df.columns.get_level_values(0):
            return download_df[ticker]
    return pd.DataFrame()


def _download_single_ticker_history(ticker, start_time):
    try:
        single = yf.Ticker(ticker).history(
            start=start_time,
            interval="1d",
            auto_adjust=False,
            actions=True,
            repair=True,
            timeout=20,
        )
    except Exception:
        return pd.DataFrame()
    return single if isinstance(single, pd.DataFrame) else pd.DataFrame()


def download_price_div_series(ticker, start_date):
    """
    Download close/dividend history for a single ticker from yfinance.
    Returns a DataFrame indexed by business date with columns: Close, Dividends.
    """
    start_time = pd.Timestamp(start_date).strftime("%Y-%m-%d")
    try:
        df = yf.download(
            tickers=ticker,
            start=start_time,
            interval="1d",
            auto_adjust=False,
            actions=True,
            repair=True,
            progress=False,
            threads=False,
            timeout=20,
            multi_level_index=False,
        )
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        df = _download_single_ticker_history(ticker, start_time)

    if df is None or df.empty:
        return pd.DataFrame()

    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    if "Close" not in df.columns:
        return pd.DataFrame()

    if "Dividends" not in df.columns:
        df["Dividends"] = 0.0

    out = df[["Close", "Dividends"]].copy()
    return out.sort_index().asfreq("B")


###################################################################################################
def get_userdata(filename):
    """
    Reads a csv file of the users stock portfolio and loads into a dataframe.
    Column headers should be as follows:
        'Company' : Company stock ticker
        'Shares' : Number of shares bought or sold (negative number = sold)
        'Date' : Date in DD/MM/YYYY format
        'Price' : Price paid/received per share
        'Brokerage' : (Optional column) Transaction fee added to cost base/cash flow.
        'Adjustments' : (Optional column) This column allow for a cost base adjustment to be made.
        Eg, if a company restructure takes place, a portion of the cost base may be split into a
        new entity. The number entered into the 'Adjustments' column represents the portion of
        the cost base that is to be removed. I.e, a value of `-0.1` indicates a 10% reduction in
        the cost base.
    Fetches stock price data for the companies in the portfolio using yahoo_finance_API


    Parameters
    ----------
    filename : string
        filepath of csv file.

    Returns
    -------
    import_a : dataframe
        Time series dataframe containing stock purchase and sale information
    """

    # Get buy/sell data for shares from the .csv file
    import_a = pd.read_csv(filename, index_col=["Company", "Date"])

    # Drop non-required columns, drop NaN rows, drop NaN rows in index, Unstack 'Company' col
    import_a = import_a.drop(
        import_a.columns.difference(["Shares", "Price", "Brokerage", "Adjustments"]), axis=1
    ).dropna(how="all")
    import_a = import_a.loc[import_a.index.dropna()].unstack(level=0)

    # Convert index to Datetime
    import_a.index = pd.to_datetime(import_a.index, format="%d/%m/%Y")
    import_a = import_a.sort_index()

    # Set column names
    import_a.columns.rename(["Params", "Company"], inplace=True)

    # Check whether all dates in portfolio are business days. Data may not be captured if not.
    invalid_dates = []
    business_days = import_a.sort_index().asfreq(freq="B").index
    for i in import_a.index:
        if i not in business_days:
            invalid_dates.append(i.strftime("%Y-%m-%d"))
    if invalid_dates:
        raise ValueError(
            "All transaction dates must be business days. Invalid date(s): "
            + ", ".join(invalid_dates)
        )

    return import_a


def merge_pricedata(portfolio, index):
    """
    Reads portfolio dataframe generated by get_userdata(), and extracts a list of stock tickers in
    the portfolio. Use API to get time series stock price data for the stocks listed and merge price
    data with the portfolio dataframe. The returned dataframe is indexed as a time series, with
    business day frequency.


    Parameters
    ----------
    portfolio : pandas.DataFrame
        portfolio dataframe generated by get_userdata().
    index : string
        stock ticker to compare portfolio performance. Typically this would be the ticker
        of an ETF that tracks an index, eg "SPY" which tracks the S&P 500 index.

    Returns
    -------
    import_a : pandas.DataFrame
        Time series dataframe containing stock purchase and sale information, merged with stock
        price data over the time frame convered by the portfolio

    """

    # Portfolio start and end time for extracting data using API
    start_date = min(portfolio.index)
    start_time = start_date.strftime("%Y-%m-%d")
    # start_time = int(start_date.timestamp())
    # end_time = datetime.today().replace(second=0, microsecond=0).strftime("%m/%d/%Y")

    # Fetch stock prices using API and merge with trading data
    print("\nAPI call in progress...\n")
    fetched_tickers = []
    failed_tickers = {}

    # Extract list of portfolio tickers
    tickers = list(dict.fromkeys(list(portfolio.columns.levels[1]) + [index]))
    if not tickers:
        return portfolio

    try:
        batch = yf.download(
            tickers=tickers,
            start=start_time,
            interval="1d",
            auto_adjust=False,
            actions=True,
            repair=True,
            progress=False,
            threads=False,
            timeout=20,
            group_by="ticker",
            multi_level_index=True,
        )
    except Exception as exc:
        for t in tickers:
            failed_tickers[t] = f"batch request error: {type(exc).__name__}"
        batch = pd.DataFrame()

    # If batch is empty, retry per ticker to avoid an all-or-nothing failure.
    if batch is None or batch.empty:
        for t in tickers:
            inputdata = _download_single_ticker_history(t, start_time)
            if inputdata is None or inputdata.empty:
                failed_tickers[t] = "no rows returned"
                continue
            if isinstance(inputdata.index, pd.DatetimeIndex) and inputdata.index.tz is not None:
                inputdata.index = inputdata.index.tz_localize(None)
            if "Close" not in inputdata.columns:
                failed_tickers[t] = "missing Close column"
                continue
            if "Dividends" not in inputdata.columns:
                inputdata["Dividends"] = 0
            cols = pd.MultiIndex.from_arrays([["$", "Div"], [t, t]], names=["Params", "Company"])
            df = pd.DataFrame(
                inputdata[["Close", "Dividends"]].values,
                index=inputdata.index,
                columns=cols,
            )
            portfolio = pd.merge(portfolio, df, how="outer", left_index=True, right_index=True).drop_duplicates()
            fetched_tickers.append(t)

        batch = None  # signal that fallback handled merging

    single_ticker = len(tickers) == 1
    if batch is not None:
        for i in tickers:
            inputdata = _extract_ticker_history(batch, i, single_ticker=single_ticker)
            if inputdata is None or inputdata.empty:
                failed_tickers[i] = "no rows returned"
                print(f"Warning: no data returned for {i}. Skipping...")
                continue

            if "Close" not in inputdata.columns:
                failed_tickers[i] = "missing Close column"
                print(f"Warning: missing Close column for {i}. Skipping...")
                continue

            if isinstance(inputdata.index, pd.DatetimeIndex) and inputdata.index.tz is not None:
                inputdata.index = inputdata.index.tz_localize(None)

            cols = pd.MultiIndex.from_arrays(
                [["$", "Div"], [i, i]], names=["Params", "Company"]
            )

            if "Dividends" not in inputdata.columns:
                inputdata["Dividends"] = 0

            df = pd.DataFrame(
                inputdata[["Close", "Dividends"]].values,
                index=inputdata.index,
                columns=cols,
            )

            portfolio = pd.merge(
                portfolio, df, how="outer", left_index=True, right_index=True
            ).drop_duplicates()
            fetched_tickers.append(i)

    print("API call complete\n")
    if failed_tickers:
        print("Warning: some tickers failed to fetch:")
        for ticker, reason in failed_tickers.items():
            print(f"  - {ticker}: {reason}")

    # Set to 'Business day' datetime frequency
    portfolio = portfolio.sort_index().asfreq(freq="B")
    portfolio.attrs["price_fetch"] = {
        "provider": "yfinance",
        "fetched": fetched_tickers,
        "failed": failed_tickers,
    }

    # Set accumulated shares for the index to 1, to simplify later calculations
    # portfolio[('Accum', index)] = int(1)

    return portfolio



def process_data(portfolio):
    """
    Reads portfolio dataframe generated by merge_stockdata(), and performs basic processing of the
    data including handling of NaN values and adding the following time series indexed columns to
    the dataframe:
        Accum: Accumulated share holdings
        Val: Dollar value of each stock holdings
        Buy_amt: Dollar amount cash folws in and out of portfolio


    Parameters
    ----------
    portfolio : pandas.DataFrame
        portfolio dataframe generated by get_stockdata().

    Returns
    -------
    import_a : pandas.DataFrame
        Time series dataframe containing stock purchase and sale information, merged with stock
        price data over the time frame convered by the portfolio

    """
    # Define IndexSlice for dataframe slicing
    idx = pd.IndexSlice
    available_params = set(portfolio.columns.get_level_values("Params"))
    required_params = {"$", "Div", "Price", "Shares"}
    missing_params = sorted(required_params - available_params)
    if missing_params:
        raise ValueError(
            "Merged portfolio is missing required data columns: "
            + ", ".join(missing_params)
            + ". Price provider may have returned no market data."
        )

    # Tickers from the portfolio and including the index
    portfolio_cols = portfolio["Shares"].columns
    # Handle Na values.
    portfolio["$"] = portfolio["$"].ffill().fillna(0)
    fill_params = ["Shares", "Price", "Div"]
    if "Brokerage" in available_params:
        fill_params.append("Brokerage")
    portfolio.loc[:, idx[fill_params, :]] = portfolio.loc[
        :, idx[fill_params, :]
    ].fillna(0)
    # Accumulated shares
    Accum = (
        portfolio["Shares"][~np.isnan(portfolio["Shares"])].cumsum().ffill().fillna(0)
    )
    Accum.columns = pd.MultiIndex.from_product(
        [["Accum"], portfolio_cols], names=["Params", "Company"]
    )
    # Current val of each stock holding
    Val = portfolio["$"] * Accum
    # Cash flows into portfolio
    Buy_amt = (portfolio["Price"] * portfolio["Shares"]).fillna(0)
    if "Brokerage" in portfolio.columns:
        Buy_amt = Buy_amt + portfolio["Brokerage"][portfolio_cols].fillna(0)
    # Dividend series (used directly when no adjustment column exists)
    Div = portfolio["Div"][portfolio_cols]

    if "Adjustments" in portfolio.columns:

        # Cash flow adjustments due to demerger/acquisition event.
        portfolio.loc[:, idx["Adjustments", :]] = portfolio.loc[
            :, idx["Adjustments", :]
        ].fillna(0)
        # Use .loc for Adjustments to maintain the multiindex columns
        Buy_amt = Buy_amt + portfolio.loc[:, idx["Adjustments", :]] * Buy_amt.cumsum()
        # For use in div_tot calc.
        Div = (
            portfolio["Div"][portfolio_cols]
            + portfolio["Adjustments"][portfolio_cols]
            * portfolio["Div"][portfolio_cols].cumsum()
        )

    # Keep company-only dividend columns for Div_tot calculation
    div_base = Div.copy()

    # reset column names
    for val, val_name in zip([Val, Buy_amt, Div], ["Val", "Buy_amt", "Div"]):
        val.columns = pd.MultiIndex.from_product(
            [[val_name], portfolio_cols], names=["Params", "Company"]
        )
    # Total dollar value of dividend
    Div_tot = (div_base * Accum.droplevel("Params", axis=1)).round(2)
    Div_tot.columns = pd.MultiIndex.from_product(
        [["Div_tot"], portfolio_cols], names=["Params", "Company"]
    )
    # Concatenate processed data with original dataframe
    portfolio = pd.concat([portfolio, Buy_amt, Accum, Val, Div_tot], axis=1)

    return portfolio


def convert_currency(merged_portfolio, target_currency):
    
    # Avoid in-place modification of the 
    converted_portfolio = merged_portfolio.copy()
    # Extract tickers from the merged portfolio
    tickers = converted_portfolio.columns.get_level_values('Company').unique()
    fx_cache = {}
    fx_rates_by_ticker = {}
    
    # Get currencies for each ticker
    currencies = {}
    for ticker in tickers:
        try:
            ticker_obj = yf.Ticker(ticker)
            metadata = ticker_obj.get_history_metadata() or {}
            currency = metadata.get("currency")
            if not currency:
                # fast_info can still provide currency when metadata is incomplete
                try:
                    currency = ticker_obj.fast_info.get("currency")
                except Exception:
                    currency = None
            if not currency:
                raise ValueError("currency metadata unavailable")
            currencies[ticker] = currency
        except Exception as exc:
            warnings.warn(
                f"Could not determine currency for {ticker}; leaving unchanged. ({type(exc).__name__})",
                RuntimeWarning,
            )
            continue
    
    # Get the start and end date for the entire portfolio
    start_date = converted_portfolio.index.min()
    
    for ticker, base_currency in currencies.items():
        if base_currency != target_currency:
            # Fetch exchange rate data for the entire portfolio date range
            try:
                pair = (base_currency, target_currency)
                if pair not in fx_cache:
                    fx_df = yf.download(
                        f"{base_currency}{target_currency}=X",
                        start=start_date,
                        progress=False,
                        threads=False,
                        auto_adjust=False,
                        multi_level_index=False,
                        timeout=20,
                    )
                    if "Close" not in fx_df.columns:
                        raise ValueError("missing Close column")

                    close_col = fx_df["Close"]
                    if isinstance(close_col, pd.DataFrame):
                        if close_col.shape[1] == 0:
                            raise ValueError("empty FX close matrix")
                        close_col = close_col.iloc[:, 0]

                    exchange_rate = (
                        close_col.asfreq(freq="B").ffill().reindex(converted_portfolio.index).ffill()
                    )
                    if exchange_rate.isna().all():
                        raise ValueError("empty FX rate series")
                    fx_cache[pair] = exchange_rate
                exchange_rate = fx_cache[pair]
            except Exception as exc:
                warnings.warn(
                    f"FX download failed for {base_currency}->{target_currency}; leaving {ticker} unchanged. ({type(exc).__name__})",
                    RuntimeWarning,
                )
                continue
            
            # Apply exchange rate to relevant columns for this ticker
            for param in ['$', 'Price', 'Val', 'Buy_amt', 'Div_tot', 'Div']:
                column = (param, ticker)
                if column in converted_portfolio.columns:
                    converted_portfolio.loc[:, column] = converted_portfolio.loc[:, column] * exchange_rate
            fx_rates_by_ticker[ticker] = exchange_rate.copy()
    if fx_rates_by_ticker:
        fx_rates_df = pd.DataFrame(fx_rates_by_ticker).reindex(converted_portfolio.index).ffill()
    else:
        fx_rates_df = pd.DataFrame(index=converted_portfolio.index)
    converted_portfolio.attrs["fx_rates"] = fx_rates_df
    converted_portfolio.attrs["target_currency"] = target_currency
    return converted_portfolio


def extract_parameters(processed_portfolio):
    """
    Reads portfolio dataframe generated by process_data() and extracts separate time series
    indexed dataframes representing various parameters, that can be used in functions to calculate
    share/portfolio performance metrics.


    Parameters
    ----------
    processed_portfolio : pandas.DataFrame
        portfolio dataframe generated by process_data().

    Returns
    -------
    val, cash_flows, price, accum, shares: pandas.DataFrames
        val: Dollar value of each stock holdings
        cash_flows: Dollar amount cash flows in and out of portfolio
        price: Share price data
        accum: Accumulated share holdings
        shares: number of shares bought or sold
    """

    val = processed_portfolio["Val"]
    cash_flows = processed_portfolio["Buy_amt"]
    price = processed_portfolio["$"]
    accum = processed_portfolio["Accum"]
    shares = processed_portfolio["Shares"]
    div_tot = processed_portfolio["Div_tot"]
    div = processed_portfolio["Div"]

    return val, cash_flows, price, accum, shares, div_tot, div


"""        
        # Average price. Replace inf values (may exist if accum = 0) with 0
        df[col+'_avg_price'] = (df[col + '_buy_amt'][df[col+'_buy_amt']>0].cumsum() / 
                                 df[col+'_n'][df[col+'_n']>0].cumsum())
        df[col+'_avg_price'] = df[col+'_avg_price'].ffill()
        
        if adjustments_exist == True:
            df[col+'_avg_price'] = df[col+'_avg_price'] * (1 + df[col+'_adj'])
    
"""


###################################################################################################


def stock_summary(portfolio, index, date=None, styles=True, calc_method="basic", currency=None):

    # Test for portfolio of single stock. (iloc[-1].values line will retuen an error)
    """
    Generates a summary table for portfolio and individual stock performance metrics.

    Stock-level metrics include:
        - Average purchase price (reported in base currency if specified)
        - Current market price (reported in base currency if specified)
        - Current number of shares held (not currency-dependent)
        - Current market value (reported in base currency if specified)
        - Daily percentage return (not currency-dependent)
        - Total return (basic return) (not currency-dependent)
        - Annualized return (annualized basic return) (not currency-dependent)

    Portfolio-level metrics include:
        - Current total market value (reported in base currency if specified)
        - Daily percentage return (not currency-dependent)
        - Total return (basic return) (not currency-dependent)
        - Annualized return (annualized basic return) (not currency-dependent)

    The benchmark index (specified by the 'index' parameter) is used for comparison 
    purposes only and its performance is not affected by the base currency.

    Parameters
    ----------
    portfolio : pandas.DataFrame
        Dataframe containing portfolio data.
    index : str
        Ticker symbol of the benchmark index to compare portfolio performance against.
    date : str, optional
        Date to truncate the data. Defaults to None.
    styles : bool, optional
        Flag to include dataframe styles. Defaults to True.
    calc_method : str, optional
        Method to use for calculating returns. Defaults to 'basic'.
    currency : str, optional
        Currency to use for calculations. Defaults to None. If specified, metrics that 
        are currency-dependent will be reported in this currency.

    Returns
    -------
    di : pandas.DataFrame
        Dataframe containing the summary metrics.
    """
        
    if currency:
        portfolio = convert_currency(portfolio, target_currency=currency)

    val_full, cash_flows_full, price_full, accum_full, shares_full, div_tot_full, div_full = extract_parameters(portfolio)
    init_CF = price_full.shape == price_full[date:].shape

    price_all = price_full[date:]
    val = val_full.loc[date:].ffill()
    cash_flows = cash_flows_full.loc[date:].ffill()
    price = price_full.loc[date:].ffill()
    accum = accum_full.loc[date:].ffill()
    shares = shares_full.loc[date:].ffill()
    div_tot = div_tot_full.loc[date:].ffill()
    div = div_full.loc[date:].ffill()

    def _last_scalar(result):
        if isinstance(result, pd.DataFrame):
            return float(result.iloc[-1, 0])
        if isinstance(result, pd.Series):
            return float(result.iloc[-1])
        return float(result)

    df = pd.DataFrame()
    df.index.name = "Company"
    benchmark_available = index in price.columns

    avg_price = calc.average_price(cash_flows_full, shares_full).ffill().reindex(val.index).ffill().fillna(0)
    df["Average Price"] = avg_price.iloc[-1]
    df["Current Price"] = price.iloc[-1]
    df["Current Holdings"] = accum.iloc[-1]
    df["Current Value"] = val.iloc[-1]
    daily_base = calc.daily_pct_gain(price_all.drop(labels=index, axis=1, errors="ignore")).ffill()
    if isinstance(daily_base, pd.DataFrame) and not daily_base.empty:
        df["Daily Return (%)"] = daily_base.iloc[-1] * 100
    elif isinstance(daily_base, pd.Series) and not daily_base.empty:
        df["Daily Return (%)"] = daily_base.iloc[-1] * 100
    else:
        df["Daily Return (%)"] = 0.0
    df.loc[df["Current Holdings"] == 0, "Daily Return (%)"] = 0

    if calc_method == "basic":
        total_ret = calc.basic_return(val, cash_flows, use_initial_CF=init_CF)
        ann_ret = calc.basic_return_annualised(val, cash_flows, use_initial_CF=init_CF)
        twr = calc.time_weighted_return(val, cash_flows, use_initial_CF=init_CF)
        ann_twr = calc.time_weighted_return_annualised(val, cash_flows, use_initial_CF=init_CF)
        dwr_last = calc.dollar_weighted_return_endpoint(val, cash_flows, use_initial_CF=init_CF)
    elif calc_method == "total":
        total_ret = calc.basic_total_return(val, cash_flows, div_tot, use_initial_CF=init_CF)
        ann_ret = calc.basic_total_return_annualised(val, cash_flows, div_tot, use_initial_CF=init_CF)
        twr = calc.time_weighted_total_return(val, cash_flows, div_tot, use_initial_CF=init_CF)
        ann_twr = calc.time_weighted_total_return_annualised(val, cash_flows, div_tot, use_initial_CF=init_CF)
        dwr_last = calc.dollar_weighted_total_return_endpoint(val, cash_flows, div_tot, use_initial_CF=init_CF)
    else:
        raise ValueError('Invalid calculation method. Please choose "basic" or "total".')

    dwr_last = dwr_last.reindex(val.columns).fillna(0)
    years_last = calc._elapsed_years_from_first_nonzero(val).iloc[-1].reindex(val.columns).replace(0, np.nan)
    ann_dwr_last = (np.power(1 + dwr_last, 1 / years_last) - 1).replace([np.inf, -np.inf], np.nan).fillna(0)

    df["Total Return (%)"] = total_ret.iloc[-1].values * 100
    df["Ann. Return (%)"] = ann_ret.iloc[-1].values * 100
    df["TWR (%)"] = twr.iloc[-1].values * 100
    df["Ann. TWR (%)"] = ann_twr.iloc[-1].values * 100
    df["DWR (%)"] = dwr_last.values * 100
    df["Ann. DWR (%)"] = ann_dwr_last.values * 100

    df = df.sort_index().reset_index()

    end_idx = len(df.index)
    df.loc[end_idx, "Company"] = "TOTAL"
    df.loc[end_idx, "Current Value"] = df["Current Value"].sum()
    df.loc[end_idx, "Daily Return (%)"] = calc.daily_portfolio_pct_gain(val, price).iloc[-1] * 100

    total_val = val.sum(axis=1)
    total_cf = cash_flows.sum(axis=1)
    total_div = div_tot.sum(axis=1)

    if calc_method == "basic":
        total_ret_s = calc.basic_return(total_val, total_cf, use_initial_CF=init_CF)
        ann_ret_s = calc.basic_return_annualised(total_val, total_cf, use_initial_CF=init_CF)
        twr_s = calc.time_weighted_return(total_val, total_cf, use_initial_CF=init_CF)
        ann_twr_s = calc.time_weighted_return_annualised(total_val, total_cf, use_initial_CF=init_CF)
        dwr_s = float(calc.dollar_weighted_return_endpoint(total_val, total_cf, use_initial_CF=init_CF).iloc[0])
    else:
        total_ret_s = calc.basic_total_return(total_val, total_cf, total_div, use_initial_CF=init_CF)
        ann_ret_s = calc.basic_total_return_annualised(total_val, total_cf, total_div, use_initial_CF=init_CF)
        twr_s = calc.time_weighted_total_return(total_val, total_cf, total_div, use_initial_CF=init_CF)
        ann_twr_s = calc.time_weighted_total_return_annualised(total_val, total_cf, total_div, use_initial_CF=init_CF)
        dwr_s = float(calc.dollar_weighted_total_return_endpoint(total_val, total_cf, total_div, use_initial_CF=init_CF).iloc[0])
    years_total = calc._elapsed_years_from_first_nonzero(total_val).iloc[-1]
    ann_dwr_s = (np.power(1 + dwr_s, 1 / years_total) - 1) if years_total > 0 else 0.0

    df.loc[end_idx, "Total Return (%)"] = _last_scalar(total_ret_s) * 100
    df.loc[end_idx, "Ann. Return (%)"] = _last_scalar(ann_ret_s) * 100
    df.loc[end_idx, "TWR (%)"] = _last_scalar(twr_s) * 100
    df.loc[end_idx, "Ann. TWR (%)"] = _last_scalar(ann_twr_s) * 100
    df.loc[end_idx, "DWR (%)"] = dwr_s * 100
    df.loc[end_idx, "Ann. DWR (%)"] = ann_dwr_s * 100

    df.loc[len(df.index)] = np.nan
    df.loc[len(df.index) - 1, "Company"] = ""

    if benchmark_available:
        end_idx = len(df.index)
        benchmark_cf = pd.Series(0, index=price[index].index, name=price[index].name)
        df.loc[end_idx, "Company"] = "BENCHMARK (" + index + ")"
        df.loc[end_idx, "Daily Return (%)"] = calc.daily_pct_gain(price[index]).iloc[-1] * 100

        if calc_method == "basic":
            bench_total = calc.basic_return(price[index], benchmark_cf)
            bench_ann = calc.basic_return_annualised(price[index], benchmark_cf)
            bench_dwr = float(calc.dollar_weighted_return_endpoint(price[index], benchmark_cf).iloc[0])
        else:
            bench_total = calc.basic_total_return(price[index], benchmark_cf, div[index])
            bench_ann = calc.basic_total_return_annualised(price[index], benchmark_cf, div[index])
            bench_dwr = float(calc.dollar_weighted_total_return_endpoint(price[index], benchmark_cf, div[index]).iloc[0])
        years_bench = calc._elapsed_years_from_first_nonzero(price[index]).iloc[-1]
        bench_ann_dwr = (np.power(1 + bench_dwr, 1 / years_bench) - 1) if years_bench > 0 else 0.0
        df.loc[end_idx, "Total Return (%)"] = _last_scalar(bench_total) * 100
        df.loc[end_idx, "Ann. Return (%)"] = _last_scalar(bench_ann) * 100
        # Leave benchmark TWR/DWR fields blank for clearer benchmark reporting semantics.
        df.loc[end_idx, "TWR (%)"] = np.nan
        df.loc[end_idx, "Ann. TWR (%)"] = np.nan
        df.loc[end_idx, "DWR (%)"] = np.nan
        df.loc[end_idx, "Ann. DWR (%)"] = np.nan

    # Normalize explicit None values so tables render blanks.
    df = df.replace({None: np.nan, "None": np.nan})

    if styles:
        cmap = sns.diverging_palette(20, 145, s=60, as_cmap=True)
        pct_cols = ["Total Return (%)", "TWR (%)", "DWR (%)"]
        ann_cols = ["Ann. Return (%)", "Ann. TWR (%)", "Ann. DWR (%)"]
        benchmark_row = len(df) - 1

        df = (
            df.style.format(
                na_rep="",
                formatter={
                    "Average Price": "{:.4f}",
                    "Current Price": "{:.2f}",
                    "Current Holdings": "{:.0f}",
                    "Current Value": "{:.2f}",
                    "Daily Return (%)": "{:.2f}",
                    "Total Return (%)": "{:.2f}",
                    "Ann. Return (%)": "{:.2f}",
                    "TWR (%)": "{:.2f}",
                    "Ann. TWR (%)": "{:.2f}",
                    "DWR (%)": "{:.2f}",
                    "Ann. DWR (%)": "{:.2f}",
                },
            )
            .background_gradient(cmap=cmap, vmin=-2, vmax=2, subset=(slice(len(df) - 3), "Daily Return (%)"))
            .background_gradient(cmap=cmap, vmin=-100, vmax=100, subset=(slice(len(df) - 3), pct_cols))
            .background_gradient(cmap=cmap, vmin=-10, vmax=10, subset=(slice(len(df) - 3), ann_cols))
            .background_gradient(cmap=cmap, vmin=-2, vmax=2, subset=(benchmark_row, "Daily Return (%)"))
            .background_gradient(cmap=cmap, vmin=-100, vmax=100, subset=(benchmark_row, ["Total Return (%)"]))
            .background_gradient(cmap=cmap, vmin=-10, vmax=10, subset=(benchmark_row, ["Ann. Return (%)"]))
        )

    return df.fillna("") if not styles else df
