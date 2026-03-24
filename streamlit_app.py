import share_tracking as share
import graphs as graph
import streamlit as st
import os
import pandas as pd
import numpy as np
import data_provider as dp
import warnings
import re
from collections import defaultdict
import seaborn as sns
import yfinance as yf
import plotly.graph_objects as go
import performance_calcs as calc

# Basic webpage setup
st.set_page_config(
   page_title="Portfolio Tracker",
   layout="wide",
   initial_sidebar_state="expanded",
)

# import stock index data
indices = pd.read_csv('stock_indices.csv')
indices = tuple(['Enter manually'] + list(indices['Symbol'] + ': ' + indices['Name']))

currencies = pd.read_csv('currencies.csv')
currencies = tuple(['Enter manually'] + list(currencies['Symbol'] + ': ' + currencies['Name']))


def _render_dataframe(data, stretch=True, **kwargs):
    """
    Streamlit compatibility wrapper:
    - Newer versions: width='stretch'
    - Older versions: use_container_width=True
    """
    if stretch:
        try:
            return st.dataframe(data, width="stretch", **kwargs)
        except TypeError:
            return st.dataframe(data, use_container_width=True, **kwargs)
    return st.dataframe(data, **kwargs)


def _render_plotly(fig, stretch=True, **kwargs):
    if stretch:
        try:
            return st.plotly_chart(fig, width="stretch", **kwargs)
        except TypeError:
            return st.plotly_chart(fig, use_container_width=True, **kwargs)
    return st.plotly_chart(fig, **kwargs)


def get_data(file, index):
    """
    Get stock data using the configured data provider.
    
    Parameters
    ----------
    file : str
        Path to the portfolio CSV file
    index : str
        Index ticker symbol
    """
    with st.sidebar:
        with st.spinner('Collecting share price data'):
            user_portfolio = share.get_userdata(file)
            merged_portfolio = dp.merge_pricedata(user_portfolio, index)
        fetch_meta = merged_portfolio.attrs.get("price_fetch", {})
        fetched = fetch_meta.get("fetched", [])
        failed = fetch_meta.get("failed", {})
        params = set(merged_portfolio.columns.get_level_values("Params"))
        provider = fetch_meta.get("provider", dp.get_data_provider())

        if "$" not in params:
            st.warning(
                f"No market price data was returned by provider '{provider}'. "
                "Portfolio transactions were loaded, but price-based metrics cannot be calculated."
            )
        elif failed:
            st.warning(
                f"Price data loaded with partial failures. "
                f"Fetched: {len(fetched)} ticker(s), Failed: {len(failed)} ticker(s)."
            )
        else:
            st.success('Success')
        st.session_state["provider_diagnostics"] = {
            "provider": provider,
            "requested_index": index,
            "fetched": fetched,
            "failed": failed,
        }
    
    return merged_portfolio
            

def process_data(merged_portfolio, target_currency, selected_index=None):
    
    # Perform initial processing of portfolio data
    try:
        portfolio = share.process_data(merged_portfolio)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", RuntimeWarning)
            portfolio = share.convert_currency(portfolio, target_currency=target_currency)
    except Exception as exc:
        st.error(f"Data processing failed ({type(exc).__name__}: {exc})")
        return False

    fx_warnings = []
    for w in caught:
        msg = str(w.message)
        if "FX" in msg or "currency" in msg.lower():
            fx_warnings.append(msg)
    fx_pair_failures = defaultdict(set)
    unknown_currency_tickers = set()
    other_fx_messages = set()

    for msg in fx_warnings:
        fx_match = re.search(r"for ([A-Z]{3})->([A-Z]{3}); leaving ([^ ]+) unchanged", msg)
        if fx_match:
            pair = f"{fx_match.group(1)}->{fx_match.group(2)}"
            fx_pair_failures[pair].add(fx_match.group(3))
            continue

        unknown_match = re.search(r"Could not determine currency for ([^;]+);", msg)
        if unknown_match:
            unknown_currency_tickers.add(unknown_match.group(1))
            continue

        other_fx_messages.add(msg)

    for pair, tickers in sorted(fx_pair_failures.items()):
        st.warning(
            f"FX conversion unavailable for {pair}. "
            f"Left {len(tickers)} ticker(s) unchanged: {', '.join(sorted(tickers))}."
        )

    if unknown_currency_tickers:
        st.warning(
            "Currency metadata unavailable for "
            + ", ".join(sorted(unknown_currency_tickers))
            + ". Left unchanged."
        )

    for msg in sorted(other_fx_messages):
        st.warning(msg)

    st.session_state["fx_diagnostics"] = {
        "target_currency": target_currency,
        "pair_failures": {k: sorted(v) for k, v in fx_pair_failures.items()},
        "unknown_currency_tickers": sorted(unknown_currency_tickers),
        "other_messages": sorted(other_fx_messages),
    }

    st.session_state['portfolio'] = portfolio
    st.session_state["portfolio_version"] = st.session_state.get("portfolio_version", 0) + 1
    if selected_index:
        st.session_state["loaded_benchmark"] = selected_index
    # New dataset loaded: reset date controls to the new portfolio start.
    new_start = pd.Timestamp(portfolio.index.min())
    st.session_state["start_date"] = new_start
    st.session_state["reset_start_date_input"] = True
    st.session_state.pop("render_cache", None)
    st.session_state.pop("render_cache_key", None)
    return True


def display_calc_details():
    with st.expander(":question: Calculation  \ndetails", expanded=False):
        st.markdown('Some of the following metrics are used to characterise the portfolio:')
        st.markdown('1. **Price Return**: % return from share price changes only.')
        st.markdown('2. **Total Return**: includes share price changes plus dividends.')
        st.markdown('3. **Basic Return**: gain divided by invested capital, with interim cash flows treated as if invested from period start.')
        st.markdown('4. **TWR (%)**: time-weighted return, designed to reduce the impact of cash-flow timing.')
        st.markdown('5. **DWR (%)**: dollar-weighted return (IRR-style), reflects the timing and size of invested dollars.')
        st.markdown('6. **Ann.** columns: annualized equivalents of the corresponding return measures.')
        st.markdown('7. **Dividend Metrics tab**:')
        st.markdown('Cumulative Dividends = running total dividend cash received.')
        st.markdown('Trailing 12M Dividends = dividend cash received over the last 12 months.')
        st.markdown('TTM Yield on Cost (%) = trailing-12M dividends / cumulative buy cash flows.')
        st.markdown('Lifetime Div/Cost (%) = cumulative dividends / cumulative buy cash flows.')
        st.markdown('8. **Attribution tab**: per-ticker contribution decomposition into price, dividend, and FX components.')
        st.markdown('9. **Rolling Returns tab**: rolling 1Y/3Y/5Y portfolio and benchmark comparison.')
        st.markdown('10. **Diagnostics tab**: provider/FX status plus stale-price and missing-data checks.')
        st.markdown('\nhttps://www.kitces.com/blog/twr-dwr-irr-calculations-performance-reporting-software-methodology-gips-compliance/')

def display_readme():
    st.image(os.path.join('screenshots','banner.png'))
    st.image(os.path.join('screenshots','st_title.png'))   
    st.text('')
    st.markdown('##### Portfolio tracker tracks the performance of a portfolio of shares against a benchmark index.  \n'
                'The user\'s share portfolio should be saved as a csv file. Details of how to format the file are given below.')
    st.text('')
    st.subheader('CSV file details :point_down:')
    st.image(os.path.join('screenshots','csv_example.png'))
    st.markdown('**Company:** Company stock ticker')
    st.markdown('The stock ticker needs to recognised by Yahoo finance. If unsure, check on the Yahoo finance website.')
    st.markdown('**Shares:** Number of shares bought or sold (negative number = sold)')
    st.markdown('**Date:** Date in DD/MM/YYYY format')
    st.markdown('**Price:** Price paid/received per share.')
    st.markdown('**Brokerage:** (Optional) Transaction fee. Included in cost base and cash-flow calculations.')
    st.markdown('**Adjustments:** (Optional column) This column allow for a cost base adjustment to be made. Eg, if a company restructure takes place,') 
    st.markdown('a portion of the cost base may be split into a new entity. The number entered into the \'_Adjustments_\' column represents')
    st.markdown('the portion of the cost base that is to be removed. I.e, a value of `-0.1` indicates a 10% reduction in the cost base.')
    

def _build_fx_return_series(val, fx_rates, scope=None):
    if fx_rates is None or fx_rates.empty:
        return None

    if scope is not None:
        if scope not in fx_rates.columns:
            return None
        fx_col = pd.to_numeric(fx_rates[scope], errors="coerce")
        fx_col = fx_col.reindex(val.index).ffill()
        first_valid = fx_col.first_valid_index()
        if first_valid is None:
            return None
        base_rate = fx_col.loc[first_valid]
        if pd.isna(base_rate) or base_rate == 0:
            return None
        return (fx_col / base_rate - 1.0) * 100.0

    converted_cols = [c for c in val.columns if c in fx_rates.columns]
    if not converted_cols:
        return None

    fx = fx_rates[converted_cols].apply(pd.to_numeric, errors="coerce").reindex(val.index).ffill()
    first_rates = fx.iloc[0].replace(0, np.nan)
    fx_ret = fx.divide(first_rates, axis=1) - 1.0

    start_vals = pd.to_numeric(val[converted_cols].iloc[0], errors="coerce").clip(lower=0).fillna(0)
    if start_vals.sum() > 0:
        weights = start_vals / start_vals.sum()
    else:
        weights = pd.Series(1.0 / len(converted_cols), index=converted_cols)

    return (fx_ret * weights).sum(axis=1, min_count=1) * 100.0


@st.cache_data(ttl=21600, show_spinner=False)
def _fetch_dividend_schedule(tickers, start_date):
    start_ts = pd.Timestamp(start_date)
    schedule_rows = []
    summary_rows = []
    warnings_out = []

    for ticker in sorted(set(tickers)):
        try:
            ticker_obj = yf.Ticker(ticker)
            ticker_currency = None
            try:
                meta = share.safe_yf_call(ticker_obj.get_history_metadata) or {}
                ticker_currency = meta.get("currency")
            except Exception:
                ticker_currency = None
            if not ticker_currency:
                try:
                    ticker_currency = share.safe_yf_call(
                        lambda: ticker_obj.fast_info.get("currency")
                    )
                except Exception:
                    ticker_currency = None
            div_series = share.safe_yf_call(lambda: ticker_obj.dividends)
            if div_series is None or len(div_series) == 0:
                warnings_out.append(f"No dividend history returned for {ticker}.")
                continue

            div_series = pd.to_numeric(div_series, errors="coerce").dropna()
            div_index = pd.to_datetime(div_series.index)
            if getattr(div_index, "tz", None) is not None:
                div_index = div_index.tz_localize(None)
            div_series.index = div_index
            div_series = div_series[div_series.index >= start_ts]
            if div_series.empty:
                warnings_out.append(
                    f"{ticker}: no dividends available on/after {start_ts.date()}."
                )
                continue

            payment_date_map = {}
            try:
                cal = share.safe_yf_call(lambda: ticker_obj.calendar)
                if isinstance(cal, pd.DataFrame) and not cal.empty:
                    cal_row = cal.iloc[0].to_dict()
                elif isinstance(cal, dict):
                    cal_row = cal
                else:
                    cal_row = {}
                ex_cal = pd.to_datetime(cal_row.get("Ex-Dividend Date"), errors="coerce")
                pay_cal = pd.to_datetime(
                    cal_row.get("Dividend Date", cal_row.get("Payment Date")),
                    errors="coerce",
                )
                if pd.notna(ex_cal) and pd.notna(pay_cal):
                    payment_date_map[pd.Timestamp(ex_cal).normalize()] = pd.Timestamp(pay_cal).normalize()
            except Exception:
                payment_date_map = {}

            div_df = pd.DataFrame(
                {
                    "Ticker": ticker,
                    "Currency": ticker_currency,
                    "Ex-Dividend Date": pd.to_datetime(div_series.index).normalize(),
                    "Dividend ($/share)": div_series.values,
                }
            )
            div_df["Payment Date"] = div_df["Ex-Dividend Date"].map(payment_date_map)
            div_df["Cumulative Dividends ($/share)"] = div_df["Dividend ($/share)"].cumsum()
            schedule_rows.append(div_df)

            cutoff = div_series.index.max() - pd.Timedelta(days=365)
            ttm_series = div_series.loc[cutoff:]
            summary_rows.append(
                {
                    "Ticker": ticker,
                    "Currency": ticker_currency,
                    "Events": int(div_series.shape[0]),
                    "Last Ex-Dividend Date": div_series.index.max().date(),
                    "Last Payment Date": (
                        div_df["Payment Date"].dropna().max().date()
                        if div_df["Payment Date"].notna().any()
                        else pd.NaT
                    ),
                    "Last Dividend ($/share)": float(div_series.iloc[-1]),
                    "TTM Dividends ($/share)": float(ttm_series.sum()),
                }
            )
        except Exception as exc:
            warnings_out.append(f"{ticker}: dividend schedule fetch failed ({type(exc).__name__}).")

    schedule_df = pd.concat(schedule_rows, ignore_index=True) if schedule_rows else pd.DataFrame()
    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(by="Ticker").reset_index(drop=True)
    if not schedule_df.empty:
        schedule_df = schedule_df.sort_values(
            by=["Ex-Dividend Date", "Ticker"], ascending=[False, True]
        ).reset_index(drop=True)

    return summary_df, schedule_df, warnings_out


@st.cache_data(ttl=21600, show_spinner=False)
def _fetch_upcoming_dividends(tickers):
    today = pd.Timestamp.today().normalize()
    rows = []
    warnings_out = []

    for ticker in sorted(set(tickers)):
        try:
            ticker_obj = yf.Ticker(ticker)
            ticker_currency = None
            try:
                meta = share.safe_yf_call(ticker_obj.get_history_metadata) or {}
                ticker_currency = meta.get("currency")
            except Exception:
                ticker_currency = None
            if not ticker_currency:
                try:
                    ticker_currency = share.safe_yf_call(
                        lambda: ticker_obj.fast_info.get("currency")
                    )
                except Exception:
                    ticker_currency = None
            cal = share.safe_yf_call(lambda: ticker_obj.calendar)
            if isinstance(cal, pd.DataFrame) and not cal.empty:
                cal_row = cal.iloc[0].to_dict()
            elif isinstance(cal, dict):
                cal_row = cal
            else:
                cal_row = {}

            ex_date = pd.to_datetime(cal_row.get("Ex-Dividend Date"), errors="coerce")
            pay_date = pd.to_datetime(
                cal_row.get("Dividend Date", cal_row.get("Payment Date")),
                errors="coerce",
            )
            if pd.notna(ex_date) and getattr(ex_date, "tzinfo", None) is not None:
                ex_date = ex_date.tz_localize(None)
            if pd.notna(pay_date) and getattr(pay_date, "tzinfo", None) is not None:
                pay_date = pay_date.tz_localize(None)
            div_per_share = pd.to_numeric(
                cal_row.get(
                    "Dividend Rate",
                    cal_row.get("Dividend", cal_row.get("Dividend Value")),
                ),
                errors="coerce",
            )

            # Keep only genuinely upcoming calendar entries.
            if pd.notna(ex_date) and ex_date.normalize() >= today:
                days_to_ex = (ex_date.normalize() - today).days
                rows.append(
                    {
                        "Ticker": ticker,
                        "Currency": ticker_currency,
                        "Upcoming Ex-Dividend Date": ex_date,
                        "Upcoming Payment Date": pay_date,
                        "Upcoming Dividend ($/share)": (
                            float(div_per_share) if pd.notna(div_per_share) else np.nan
                        ),
                        "Days to Ex-Div": days_to_ex,
                        "Source": "Calendar",
                    }
                )
                continue

            # No fallback estimation: if calendar has no upcoming ex-date, omit ticker.
        except Exception as exc:
            warnings_out.append(
                f"{ticker}: upcoming dividend calendar fetch failed ({type(exc).__name__})."
            )

    upcoming_df = pd.DataFrame(rows)
    if not upcoming_df.empty:
        # Guard against stale provider outputs.
        upcoming_df = upcoming_df[upcoming_df["Days to Ex-Div"].fillna(0) >= 0]
        upcoming_df = upcoming_df.sort_values(
            by=["Upcoming Ex-Dividend Date", "Ticker"],
            ascending=[True, True],
            na_position="last",
        ).reset_index(drop=True)
    return upcoming_df, warnings_out


@st.cache_data(ttl=21600, show_spinner=False)
def _fetch_corporate_actions(tickers, start_date):
    start_ts = pd.Timestamp(start_date)
    rows = []
    warnings_out = []

    for ticker in sorted(set(tickers)):
        try:
            ticker_obj = yf.Ticker(ticker)
            actions = share.safe_yf_call(lambda: ticker_obj.actions)
            if not isinstance(actions, pd.DataFrame) or actions.empty:
                continue

            actions = actions.copy()
            actions.index = pd.to_datetime(actions.index, errors="coerce")
            if getattr(actions.index, "tz", None) is not None:
                actions.index = actions.index.tz_localize(None)
            actions = actions[actions.index >= start_ts]
            if actions.empty:
                continue

            if "Stock Splits" in actions.columns:
                split_rows = actions[pd.to_numeric(actions["Stock Splits"], errors="coerce").fillna(0) != 0]
                for event_date, r in split_rows.iterrows():
                    split_val = pd.to_numeric(r.get("Stock Splits"), errors="coerce")
                    rows.append(
                        {
                            "Ticker": ticker,
                            "Event Type": "Split",
                            "Event Date": pd.Timestamp(event_date).date(),
                            "Details": f"Split factor: {split_val}",
                            "Action Needed": "Verify share/cost-base continuity",
                            "Status": "Open",
                        }
                    )
        except Exception as exc:
            warnings_out.append(
                f"{ticker}: corporate actions fetch failed ({type(exc).__name__})."
            )
            rows.append(
                {
                    "Ticker": ticker,
                    "Event Type": "Provider",
                    "Event Date": pd.NaT,
                    "Details": f"Corporate actions fetch failed ({type(exc).__name__})",
                    "Action Needed": "Provider check",
                    "Status": "Open",
                }
            )

    actions_df = pd.DataFrame(rows)
    if not actions_df.empty and "Event Date" in actions_df.columns:
        actions_df = actions_df.sort_values(
            by=["Event Date", "Ticker"], ascending=[False, True], na_position="last"
        ).reset_index(drop=True)
    return actions_df, warnings_out


def _period_return_series(val, cash_flows, div, benchmark_price, benchmark_div, date, mode):
    init_cf = val.shape == val[date:].shape
    if mode == "total":
        portfolio = calc.basic_total_return(
            val.sum(axis=1),
            cash_flows.sum(axis=1),
            div.sum(axis=1),
            date=date,
            use_initial_CF=init_cf,
        ) * 100.0
        benchmark = calc.basic_total_return(
            benchmark_price,
            pd.Series(0.0, index=benchmark_price.index, name=benchmark_price.name),
            benchmark_div,
            date=date,
        ) * 100.0
    else:
        portfolio = calc.basic_return(
            val.sum(axis=1),
            cash_flows.sum(axis=1),
            date=date,
            use_initial_CF=init_cf,
        ) * 100.0
        benchmark = calc.basic_return(
            benchmark_price,
            pd.Series(0.0, index=benchmark_price.index, name=benchmark_price.name),
            date=date,
        ) * 100.0
    return pd.to_numeric(portfolio, errors="coerce"), pd.to_numeric(benchmark, errors="coerce")


def _ticker_diagnostics(price_df, div_df, start_date):
    price_sel = price_df.loc[start_date:]
    div_sel = div_df.loc[start_date:]
    today = pd.Timestamp.today().normalize()
    rows = []
    for ticker in sorted(price_sel.columns):
        price_col = pd.to_numeric(price_sel[ticker], errors="coerce")
        div_col = pd.to_numeric(div_sel[ticker], errors="coerce") if ticker in div_sel.columns else pd.Series(index=price_col.index, dtype=float)
        last_valid = price_col.last_valid_index()
        stale_days = np.nan
        if last_valid is not None:
            stale_days = np.busday_count(last_valid.date(), today.date())
        rows.append(
            {
                "Ticker": ticker,
                "Last Price Date": last_valid.date() if last_valid is not None else "",
                "Stale (business days)": float(stale_days) if pd.notna(stale_days) else np.nan,
                "Price Missing (%)": float(price_col.isna().mean() * 100.0),
                "Dividend Missing (%)": float(div_col.isna().mean() * 100.0),
            }
        )
    return pd.DataFrame(rows)


def display_data():
    
    if 'portfolio' in st.session_state:     
        
        st.image(os.path.join('screenshots','banner.png'))
        if 'start_date' not in st.session_state:
            st.session_state['start_date'] = st.session_state['portfolio'].index[0]

        benchmark_ticker = st.session_state.get("loaded_benchmark", index)
        portfolio_version = st.session_state.get("portfolio_version", 0)
        render_key = (
            "subtitle_v2",
            portfolio_version,
            str(st.session_state['start_date']),
            benchmark_ticker,
        )
        subtitle_text = f"{pd.Timestamp(st.session_state['start_date']).date()} - present"
        if st.session_state.get("render_cache_key") != render_key:
            try:
                # Extract variables for performance calculations
                val, cash_flows, price, accum, shares, div, div_ = share.extract_parameters(st.session_state['portfolio'])
                fx_rates = st.session_state['portfolio'].attrs.get("fx_rates")
                benchmark_available = benchmark_ticker in price.columns
                benchmark_price = (
                    price[benchmark_ticker]
                    if benchmark_available
                    else pd.Series(1.0, index=price.index, name=benchmark_ticker)
                )
                benchmark_div = (
                    div_[benchmark_ticker]
                    if benchmark_available and benchmark_ticker in div_.columns
                    else pd.Series(0.0, index=price.index, name=benchmark_ticker)
                )
                fx_return_total = _build_fx_return_series(val, fx_rates)

                if not benchmark_available:
                    st.warning(
                        f"Benchmark ticker '{benchmark_ticker}' was not found in downloaded price data. "
                        "Benchmark comparisons are temporarily disabled for this render."
                    )

                summary_basic = share.stock_summary(
                    st.session_state['portfolio'],
                    benchmark_ticker,
                    date=st.session_state['start_date'],
                    calc_method='basic',
                )
                summary_total = share.stock_summary(
                    st.session_state['portfolio'],
                    benchmark_ticker,
                    date=st.session_state['start_date'],
                    calc_method='total',
                )

                fig1 = graph.plot_portfolio_gain_plotly(
                    val, cash_flows, benchmark_price,
                    div=div, index_div=benchmark_div,
                    date=st.session_state['start_date'],
                    calc_method='basic',
                    fx_return=fx_return_total,
                    subtitle_text=subtitle_text,
                )
                fig2 = graph.plot_portfolio_gain_plotly(
                    val, cash_flows, benchmark_price,
                    div=div, index_div=benchmark_div,
                    date=st.session_state['start_date'],
                    calc_method='total',
                    fx_return=fx_return_total,
                    subtitle_text=subtitle_text,
                )
                fig3 = graph.plot_stock_gain_plotly(
                    val,
                    cash_flows,
                    date=st.session_state['start_date'],
                    accum=accum,
                    subtitle_text=subtitle_text,
                )
                fig4 = graph.plot_stock_holdings_plotly(
                    val, date=st.session_state['start_date']
                )
                fig5 = graph.plot_annualised_return_plotly_(
                    val,
                    cash_flows,
                    benchmark_price,
                    date=st.session_state['start_date'],
                    subtitle_text=subtitle_text,
                )

                st.session_state["render_cache"] = {
                    "val": val,
                    "cash_flows": cash_flows,
                    "price": price,
                    "benchmark_price": benchmark_price,
                    "benchmark_div": benchmark_div,
                    "accum": accum,
                    "shares": shares,
                    "div": div,
                    "div_": div_,
                    "fx_rates": fx_rates,
                    "summary_basic": summary_basic,
                    "summary_total": summary_total,
                    "fig1": fig1,
                    "fig2": fig2,
                    "fig3": fig3,
                    "fig4": fig4,
                    "fig5": fig5,
                    "benchmark_status": {
                        "selected": benchmark_ticker,
                        "available": bool(benchmark_available),
                    },
                    "scope_figs": {},
                }
                st.session_state["render_cache_key"] = render_key
            except Exception as exc:
                st.error(
                    f"Failed to refresh view after benchmark change ({type(exc).__name__}: {exc})."
                )
                if "render_cache" in st.session_state:
                    st.warning("Showing last successfully rendered view.")
                else:
                    return

        if "render_cache" not in st.session_state:
            st.info("No render cache available. Click 'Get share price data' to reload.")
            return

        cache = st.session_state["render_cache"]
        val = cache["val"]
        cash_flows = cache["cash_flows"]
        price = cache["price"]
        benchmark_price = cache["benchmark_price"]
        benchmark_div = cache["benchmark_div"]
        div = cache["div"]
        div_ = cache["div_"]
        accum = cache["accum"]
        fx_rates = cache.get("fx_rates")
        fig1 = cache["fig1"]
        fig2 = cache["fig2"]
        fig3 = cache["fig3"]
        fig4 = cache["fig4"]
        fig5 = cache["fig5"]
        benchmark_status = cache.get("benchmark_status", {"selected": benchmark_ticker, "available": False})
        summary_basic = cache["summary_basic"]
        summary_total = cache["summary_total"]
        tickers = sorted(list(val.columns))
        actions_df, actions_warnings = _fetch_corporate_actions(
            tuple(tickers), st.session_state['start_date']
        )
        
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
            [
                'Portfolio Returns',
                'Stock Returns',
                'Stock details',
                'Dividend Metrics',
                'Dividend Schedule',
                'Attribution',
                'Rolling Returns',
                'Diagnostics',
            ]
        )
        
        with tab1:
            chart_scope_options = ["TOTAL"] + sorted(list(val.columns))
            if (
                "portfolio_chart_scope" in st.session_state
                and st.session_state["portfolio_chart_scope"] not in chart_scope_options
            ):
                st.session_state["portfolio_chart_scope"] = "TOTAL"
            chart_scope = st.selectbox(
                "Chart scope",
                options=chart_scope_options,
                index=0,
                key="portfolio_chart_scope",
                help="Select TOTAL portfolio or an individual stock for the return chart.",
            )

            show_total_return = st.toggle(
                "Total Return View",
                value=False,
                help="Off = Price Return, On = Total Return (includes dividends).",
            )

            if chart_scope == "TOTAL":
                scope_fig_basic = fig1
                scope_fig_total = fig2
            else:
                scope_key = (chart_scope, str(st.session_state['start_date']), benchmark_ticker)
                scope_figs = cache.get("scope_figs", {})
                if scope_key not in scope_figs:
                    val_scope = val[[chart_scope]]
                    cf_scope = cash_flows[[chart_scope]]
                    div_scope = div[[chart_scope]] if chart_scope in div.columns else pd.DataFrame(
                        {chart_scope: 0.0}, index=val_scope.index
                    )
                    # For closed positions, stop plotting after final active holding date.
                    acc_series = accum[chart_scope] if chart_scope in accum.columns else pd.Series(0.0, index=val_scope.index)
                    active_idx = acc_series[acc_series > 0].index
                    if len(active_idx) > 0 and float(acc_series.iloc[-1]) <= 1e-12:
                        cutoff = active_idx[-1]
                        val_scope = val_scope.loc[:cutoff]
                        cf_scope = cf_scope.loc[:cutoff]
                        div_scope = div_scope.loc[:cutoff]
                    benchmark_price = (
                        price[benchmark_ticker]
                        if benchmark_ticker in price.columns
                        else pd.Series(1.0, index=price.index, name=benchmark_ticker)
                    )
                    benchmark_div = (
                        div_[benchmark_ticker]
                        if benchmark_ticker in div_.columns
                        else pd.Series(0.0, index=price.index, name=benchmark_ticker)
                    )
                    if len(active_idx) > 0 and float(acc_series.iloc[-1]) <= 1e-12:
                        benchmark_price = benchmark_price.loc[:cutoff]
                        benchmark_div = benchmark_div.loc[:cutoff]
                    scope_figs[scope_key] = {
                        "basic": graph.plot_portfolio_gain_plotly(
                            val_scope,
                            cf_scope,
                            benchmark_price,
                            div=div_scope,
                            index_div=benchmark_div,
                            date=st.session_state['start_date'],
                            calc_method='basic',
                            fx_return=_build_fx_return_series(val_scope, fx_rates, scope=chart_scope),
                            subtitle_text=subtitle_text,
                        ),
                        "total": graph.plot_portfolio_gain_plotly(
                            val_scope,
                            cf_scope,
                            benchmark_price,
                            div=div_scope,
                            index_div=benchmark_div,
                            date=st.session_state['start_date'],
                            calc_method='total',
                            fx_return=_build_fx_return_series(val_scope, fx_rates, scope=chart_scope),
                            subtitle_text=subtitle_text,
                        ),
                    }
                    cache["scope_figs"] = scope_figs
                scope_fig_basic = scope_figs[scope_key]["basic"]
                scope_fig_total = scope_figs[scope_key]["total"]

            if show_total_return:
                _render_plotly(scope_fig_total)
                st.markdown("##### Summary Table")
                st.caption(subtitle_text)
                _render_dataframe(summary_total)
            else:
                _render_plotly(scope_fig_basic)
                st.markdown("##### Summary Table")
                st.caption(subtitle_text)
                _render_dataframe(summary_basic)
        
        with tab2:
            _render_plotly(fig3)
        
        with tab3:
            col1, col2 = st.columns([1, 1])
            with col1:
                _render_plotly(fig4)
            with col2:    
                _render_plotly(fig5)

        with tab4:
            div_cash = div.loc[st.session_state['start_date']:].fillna(0)
            cf_sel = cash_flows.loc[st.session_state['start_date']:].fillna(0)
            cum_div = div_cash.cumsum()

            if div_cash.empty:
                st.info("No dividend data available for the selected period.")
            else:
                col_cum_div = "Cumulative Dividends ($)"
                col_ttm_div = "Trailing 12M Dividends ($)"
                col_div_yield = "Dividend Yield (%)"
                col_ttm_yoc = "TTM Yield on Cost (%)"
                col_life_yoc = "Lifetime Div/Cost (%)"

                ttm_cutoff = div_cash.index.max() - pd.Timedelta(days=365)
                ttm_div = div_cash.loc[ttm_cutoff:].sum()
                invested = cf_sel.clip(lower=0).sum()
                current_value = val.loc[st.session_state['start_date']:].ffill().iloc[-1]
                current_value_safe = pd.to_numeric(current_value, errors="coerce").where(
                    pd.to_numeric(current_value, errors="coerce") != 0, np.nan
                )
                invested_safe = pd.to_numeric(invested, errors="coerce").where(
                    pd.to_numeric(invested, errors="coerce") != 0, np.nan
                )
                def _safe_pct(numerator, denominator):
                    den = pd.to_numeric(denominator, errors="coerce")
                    num = pd.to_numeric(numerator, errors="coerce")

                    if np.isscalar(den):
                        if pd.isna(den) or den <= 0:
                            return np.nan
                        return (num / den) * 100

                    den = den.where(den > 0, np.nan)
                    return (num / den) * 100

                dividend_yield = _safe_pct(ttm_div, current_value_safe)
                yield_on_cost_ttm = _safe_pct(ttm_div, invested_safe)
                lifetime_div_to_cost = _safe_pct(cum_div.iloc[-1], invested_safe)

                div_summary = pd.DataFrame(
                    {
                        col_cum_div: cum_div.iloc[-1],
                        col_ttm_div: ttm_div,
                        col_div_yield: dividend_yield,
                        col_ttm_yoc: yield_on_cost_ttm,
                        col_life_yoc: lifetime_div_to_cost,
                    }
                ).sort_index()
                div_summary = div_summary.replace({None: np.nan})
                total_dividend_yield = _safe_pct(ttm_div.sum(), current_value.sum())
                total_ttm_yoc = _safe_pct(ttm_div.sum(), invested.sum())
                total_life_yoc = _safe_pct(cum_div.iloc[-1].sum(), invested.sum())

                div_summary.loc["TOTAL"] = [
                    div_summary[col_cum_div].sum(),
                    div_summary[col_ttm_div].sum(),
                    float(total_dividend_yield) if pd.notna(total_dividend_yield) else np.nan,
                    float(total_ttm_yoc) if pd.notna(total_ttm_yoc) else np.nan,
                    float(total_life_yoc) if pd.notna(total_life_yoc) else np.nan,
                ]

                styled_div_summary = (
                    div_summary.style.format(
                        {
                            col_cum_div: "{:.2f}",
                            col_ttm_div: "{:.2f}",
                            col_div_yield: "{:.2f}",
                            col_ttm_yoc: "{:.2f}",
                            col_life_yoc: "{:.2f}",
                        },
                        na_rep="",
                    )
                    .background_gradient(
                        cmap=sns.diverging_palette(20, 145, s=60, as_cmap=True),
                        vmin=-10,
                        vmax=10,
                        subset=[
                            col_div_yield,
                            col_ttm_yoc,
                        ],
                    )
                    .background_gradient(
                        cmap=sns.diverging_palette(20, 145, s=60, as_cmap=True),
                        vmin=-100,
                        vmax=100,
                        subset=[col_life_yoc],
                    )
                    .highlight_null(props="background-color: transparent; color: inherit;")
                )
                st.markdown("##### Summary Table")
                st.caption(subtitle_text)
                _render_dataframe(styled_div_summary)

                div_options = ["TOTAL"] + sorted(list(div_cash.columns))
                if (
                    "div_chart_scope" in st.session_state
                    and st.session_state["div_chart_scope"] not in div_options
                ):
                    st.session_state["div_chart_scope"] = "TOTAL"
                div_selection = st.selectbox(
                    "Dividend chart scope",
                    options=div_options,
                    index=0,
                    key="div_chart_scope",
                )

                try:
                    fig_div_cum, fig_div_annual = graph.plot_dividend_metrics_plotly(
                        div_cash, selection=div_selection, subtitle_text=subtitle_text
                    )
                except Exception as exc:
                    st.error(
                        f"Dividend chart render failed for selection '{div_selection}': "
                        f"{type(exc).__name__}: {exc}"
                    )
                    fig_div_cum, fig_div_annual = graph.plot_dividend_metrics_plotly(
                        div_cash, selection="TOTAL", subtitle_text=subtitle_text
                    )

                c1, c2 = st.columns(2)
                with c1:
                    _render_plotly(fig_div_cum)
                with c2:
                    _render_plotly(fig_div_annual)

        with tab5:
            summary_df, schedule_df, sched_warnings = _fetch_dividend_schedule(
                tuple(tickers),
                st.session_state['start_date'],
            )
            upcoming_df, upcoming_warnings = _fetch_upcoming_dividends(tuple(tickers))

            provider_notes = list(sched_warnings) + list(upcoming_warnings) + list(actions_warnings)
            if provider_notes:
                with st.expander("Provider notes", expanded=False):
                    for msg in provider_notes:
                        st.warning(msg)

            if summary_df.empty and schedule_df.empty:
                st.info(
                    "No dividend schedule data available from Yahoo Finance for the selected "
                    "tickers/date range."
                )
            else:
                schedule_work = pd.DataFrame()
                has_payment_dates = False
                if not schedule_df.empty:
                    schedule_work = schedule_df.copy()
                    schedule_work["Ex-Dividend Date"] = pd.to_datetime(schedule_work["Ex-Dividend Date"])
                    schedule_work["Payment Date"] = pd.to_datetime(schedule_work["Payment Date"], errors="coerce")
                    has_payment_dates = schedule_work["Payment Date"].notna().any()
                    schedule_work["FY"] = np.where(
                        schedule_work["Ex-Dividend Date"].dt.month >= 7,
                        schedule_work["Ex-Dividend Date"].dt.year + 1,
                        schedule_work["Ex-Dividend Date"].dt.year,
                    )
                    schedule_work["Shares Held (Ex-Date)"] = 0.0
                    for ticker in schedule_work["Ticker"].unique():
                        if ticker in accum.columns:
                            tmask = schedule_work["Ticker"] == ticker
                            ex_dates = pd.DatetimeIndex(schedule_work.loc[tmask, "Ex-Dividend Date"])
                            holdings = (
                                pd.to_numeric(accum[ticker], errors="coerce")
                                .reindex(ex_dates, method="ffill")
                                .fillna(0.0)
                                .values
                            )
                            schedule_work.loc[tmask, "Shares Held (Ex-Date)"] = holdings
                    schedule_work["Dividend Value ($)"] = (
                        pd.to_numeric(schedule_work["Dividend ($/share)"], errors="coerce")
                        * pd.to_numeric(schedule_work["Shares Held (Ex-Date)"], errors="coerce")
                    )

                if not summary_df.empty:
                    if not schedule_work.empty:
                        last_div_value = (
                            schedule_work.sort_values(["Ticker", "Ex-Dividend Date"])
                            .groupby("Ticker", as_index=False)
                            .tail(1)[["Ticker", "Dividend Value ($)"]]
                            .rename(columns={"Dividend Value ($)": "Last Dividend ($)"})
                        )
                        summary_df = summary_df.merge(last_div_value, on="Ticker", how="left")
                    ordered_cols = [
                        "Ticker",
                        "Currency",
                        "Events",
                        "Last Ex-Dividend Date",
                        "Last Payment Date",
                        "Last Dividend ($/share)",
                        "Last Dividend ($)",
                        "TTM Dividends ($/share)",
                    ]
                    if (
                        "Last Payment Date" in summary_df.columns
                        and summary_df["Last Payment Date"].isna().all()
                    ):
                        summary_df = summary_df.drop(columns=["Last Payment Date"])
                    summary_df = summary_df[
                        [c for c in ordered_cols if c in summary_df.columns]
                    ]
                    styled_schedule_summary = summary_df.style.format(
                        {
                            "Last Dividend ($/share)": "{:.4f}",
                            "Last Dividend ($)": "{:.2f}",
                            "TTM Dividends ($/share)": "{:.4f}",
                        }
                    )
                    st.markdown("##### Dividend Schedule Summary")
                    st.caption(subtitle_text)
                    _render_dataframe(styled_schedule_summary)

                if not upcoming_df.empty:
                    upcoming_view = upcoming_df.copy()
                    if (
                        "Upcoming Payment Date" in upcoming_view.columns
                        and upcoming_view["Upcoming Payment Date"].isna().all()
                    ):
                        upcoming_view = upcoming_view.drop(columns=["Upcoming Payment Date"])
                    upcoming_view["Upcoming Ex-Dividend Date"] = pd.to_datetime(
                        upcoming_view["Upcoming Ex-Dividend Date"], errors="coerce"
                    ).dt.date
                    if "Upcoming Payment Date" in upcoming_view.columns:
                        upcoming_view["Upcoming Payment Date"] = pd.to_datetime(
                            upcoming_view["Upcoming Payment Date"], errors="coerce"
                        ).dt.date
                    upcoming_view["Shares Held (Ex-Date)"] = 0.0
                    for ticker in upcoming_view["Ticker"].unique():
                        if ticker in accum.columns:
                            tmask = upcoming_view["Ticker"] == ticker
                            ex_dates = pd.to_datetime(
                                upcoming_view.loc[tmask, "Upcoming Ex-Dividend Date"], errors="coerce"
                            )
                            holdings = (
                                pd.to_numeric(accum[ticker], errors="coerce")
                                .reindex(ex_dates, method="ffill")
                                .fillna(0.0)
                                .values
                            )
                            upcoming_view.loc[tmask, "Shares Held (Ex-Date)"] = holdings
                    if "Upcoming Dividend ($/share)" in upcoming_view.columns:
                        upcoming_view["Expected Dividend Cash ($)"] = (
                            pd.to_numeric(upcoming_view["Upcoming Dividend ($/share)"], errors="coerce")
                            * pd.to_numeric(upcoming_view["Shares Held (Ex-Date)"], errors="coerce")
                        )
                    st.markdown("##### Upcoming Dividends")
                    st.caption(subtitle_text)
                    upcoming_view = upcoming_view.replace({None: np.nan})
                    display_cols = [
                        c
                        for c in ["Upcoming Dividend ($/share)", "Expected Dividend Cash ($)"]
                        if c in upcoming_view.columns
                    ]
                    for c in display_cols:
                        upcoming_view[c] = pd.to_numeric(upcoming_view[c], errors="coerce")
                        upcoming_view[c] = upcoming_view[c].map(
                            lambda x: "Missing from provider" if pd.isna(x) else x
                        )
                    _render_dataframe(
                        upcoming_view.style.format(
                            {
                                "Days to Ex-Div": "{:.0f}",
                                "Shares Held (Ex-Date)": "{:.2f}",
                            }
                        )
                    )
                    if "Expected Dividend Cash ($)" in upcoming_view.columns:
                        ex_dates = pd.to_datetime(
                            upcoming_view["Upcoming Ex-Dividend Date"], errors="coerce"
                        )
                        expected_cash = pd.to_numeric(
                            upcoming_view["Expected Dividend Cash ($)"], errors="coerce"
                        ).fillna(0.0)
                        now_norm = pd.Timestamp.today().normalize()
                        next_30 = expected_cash[(ex_dates >= now_norm) & (ex_dates <= now_norm + pd.Timedelta(days=30))].sum()
                        next_90 = expected_cash[(ex_dates >= now_norm) & (ex_dates <= now_norm + pd.Timedelta(days=90))].sum()
                        future_income_summary = pd.DataFrame(
                            [
                                {
                                    "Confirmed events": int(len(upcoming_view)),
                                    "Expected cash next 30d ($)": float(next_30),
                                    "Expected cash next 90d ($)": float(next_90),
                                }
                            ]
                        )
                        st.markdown("##### Future Income Summary")
                        _render_dataframe(
                            future_income_summary.style.format(
                                {
                                    "Expected cash next 30d ($)": "{:.2f}",
                                    "Expected cash next 90d ($)": "{:.2f}",
                                }
                            )
                        )

                if not schedule_df.empty:
                    ticker_options = ["ALL"] + sorted(schedule_work["Ticker"].unique().tolist())
                    selected_ticker = st.selectbox(
                        "Dividend schedule scope",
                        options=ticker_options,
                        index=0,
                        key="div_schedule_scope",
                    )

                    fy_options = sorted(schedule_work["FY"].dropna().astype(int).unique().tolist(), reverse=True)
                    selected_fy = st.selectbox(
                        "Dividend export financial year",
                        options=fy_options,
                        index=0,
                        key="div_schedule_fy",
                        format_func=lambda y: f"FY{y} ({y-1}-07-01 to {y}-06-30)",
                    )

                    if selected_ticker == "ALL":
                        schedule_view = schedule_work
                    else:
                        schedule_view = schedule_work[schedule_work["Ticker"] == selected_ticker]

                    export_df = schedule_view[schedule_view["FY"] == selected_fy].copy()
                    export_df = export_df.sort_values(by=["Ex-Dividend Date", "Ticker"], ascending=[True, True])
                    export_df["Ex-Dividend Date"] = export_df["Ex-Dividend Date"].dt.strftime("%Y-%m-%d")
                    if has_payment_dates:
                        export_df["Payment Date"] = export_df["Payment Date"].dt.strftime("%Y-%m-%d").fillna("")
                    export_df = export_df[
                        ["Ticker", "Currency", "FY", "Ex-Dividend Date"]
                        + (["Payment Date"] if has_payment_dates else [])
                        + [
                            "Dividend ($/share)",
                            "Shares Held (Ex-Date)",
                            "Dividend Value ($)",
                            "Cumulative Dividends ($/share)",
                        ]
                    ]

                    st.download_button(
                        label="Export selected FY dividend CSV",
                        data=export_df.to_csv(index=False).encode("utf-8"),
                        file_name=f"dividend_schedule_FY{selected_fy}_{selected_ticker}.csv",
                        mime="text/csv",
                        disabled=export_df.empty,
                        help="Exports dividend event details for the selected scope and financial year.",
                    )
                    if export_df.empty:
                        st.info("No dividend events found for the selected scope and financial year.")

                    schedule_view = schedule_view.drop(columns=["FY"]).copy()
                    schedule_view["Ex-Dividend Date"] = schedule_view["Ex-Dividend Date"].dt.date
                    if has_payment_dates:
                        schedule_view["Payment Date"] = schedule_view["Payment Date"].dt.date
                    else:
                        schedule_view = schedule_view.drop(columns=["Payment Date"])
                    st.markdown("##### Dividend Events")
                    st.caption(subtitle_text)
                    _render_dataframe(
                        schedule_view.style.format(
                            {
                                "Dividend ($/share)": "{:.4f}",
                                "Shares Held (Ex-Date)": "{:.2f}",
                                "Dividend Value ($)": "{:.2f}",
                                "Cumulative Dividends ($/share)": "{:.4f}",
                            }
                        )
                    )

        with tab6:
            contrib_scope_options = ["TOTAL"] + sorted(list(val.columns))
            if (
                "contrib_scope" in st.session_state
                and st.session_state["contrib_scope"] not in contrib_scope_options
            ):
                st.session_state["contrib_scope"] = "TOTAL"
            contrib_scope = st.selectbox(
                "Attribution scope",
                options=contrib_scope_options,
                index=0,
                key="contrib_scope",
            )

            if contrib_scope == "TOTAL":
                val_attr = val
                cf_attr = cash_flows
                div_attr = div
                fx_attr = fx_rates
            else:
                val_attr = val[[contrib_scope]]
                cf_attr = cash_flows[[contrib_scope]]
                div_attr = div[[contrib_scope]] if contrib_scope in div.columns else pd.DataFrame(
                    {contrib_scope: 0.0}, index=val.index
                )
                fx_attr = (
                    fx_rates[[contrib_scope]]
                    if isinstance(fx_rates, pd.DataFrame) and contrib_scope in fx_rates.columns
                    else None
                )

            contrib_df = calc.contribution_analysis(
                val_attr,
                cf_attr,
                div_attr,
                fx_rates=fx_attr,
                date=st.session_state["start_date"],
                include_total=True,
            )
            st.markdown("##### Contribution Analysis")
            st.caption(subtitle_text)
            _render_dataframe(
                contrib_df.style.format(
                    {
                        "Price ($)": "{:.2f}",
                        "Dividend ($)": "{:.2f}",
                        "FX ($)": "{:.2f}",
                        "Total ($)": "{:.2f}",
                        "Contribution (%)": "{:.2f}",
                        "Contribution Share of Total (%)": "{:.2f}",
                    },
                    na_rep="",
                )
            )

            core = contrib_df.drop(index=["TOTAL"], errors="ignore").copy()
            if not core.empty:
                top_n = min(8, len(core))
                plot_df = pd.concat(
                    [core.nlargest(top_n, "Total ($)"), core.nsmallest(top_n, "Total ($)")]
                ).drop_duplicates()
                plot_df = plot_df.sort_values("Total ($)", ascending=True)
                bar_colors = np.where(
                    pd.to_numeric(plot_df["Total ($)"], errors="coerce") >= 0,
                    "rgb(71, 157, 201)",
                    "rgb(220, 82, 88)",
                )
                fig_attr = go.Figure()
                fig_attr.add_trace(
                    go.Bar(
                        x=plot_df["Total ($)"],
                        y=plot_df.index.astype(str),
                        name="Total Contribution ($)",
                        marker_color=bar_colors,
                        orientation="h",
                    )
                )
                fig_attr.update_layout(
                    title={"text": "Top Contributors / Detractors", "x": 0.5},
                    xaxis_title="Contribution ($)",
                    yaxis_title="Ticker",
                    margin=dict(l=50, r=30, t=70, b=60),
                )
                _render_plotly(fig_attr)

        with tab7:
            rolling_mode = st.toggle(
                "Use total return for rolling windows",
                value=True,
                key="rolling_total_mode",
            )
            mode = "total" if rolling_mode else "basic"
            p_ret, b_ret = _period_return_series(
                val,
                cash_flows,
                div,
                benchmark_price,
                benchmark_div,
                st.session_state["start_date"],
                mode=mode,
            )
            roll_port, roll_bench, roll_summary = calc.rolling_return_comparison(
                p_ret, b_ret, windows_years=(1, 3, 5), periods_per_year=261
            )

            st.markdown("##### Rolling Return Summary")
            st.caption(subtitle_text)
            if roll_summary.empty:
                st.info("Not enough history for rolling 1Y/3Y/5Y windows.")
            else:
                _render_dataframe(
                    roll_summary.style.format(
                        {"Portfolio (%)": "{:.2f}", "Benchmark (%)": "{:.2f}", "Excess (%)": "{:.2f}"}
                    )
                )

            if not roll_port.empty and not roll_bench.empty:
                fig_roll = go.Figure()
                for w in roll_port.columns:
                    fig_roll.add_trace(
                        go.Scatter(
                            x=roll_port.index,
                            y=roll_port[w],
                            mode="lines",
                            name=f"Portfolio {w}",
                        )
                    )
                    fig_roll.add_trace(
                        go.Scatter(
                            x=roll_bench.index,
                            y=roll_bench[w],
                            mode="lines",
                            name=f"Benchmark {w}",
                            line=dict(dash="dot"),
                        )
                    )
                fig_roll.update_layout(
                    title={"text": "Rolling Returns (1Y/3Y/5Y)", "x": 0.5},
                    xaxis_title="Date",
                    yaxis_title="Return (%)",
                    margin=dict(l=50, r=30, t=70, b=50),
                )
                _render_plotly(fig_roll)

        with tab8:
            st.markdown("##### Data Provider Status")
            provider_diag = st.session_state.get("provider_diagnostics", {})
            provider_rows = [
                {
                    "Provider": provider_diag.get("provider", ""),
                    "Requested Benchmark": provider_diag.get("requested_index", ""),
                    "Fetched Tickers": len(provider_diag.get("fetched", [])),
                    "Failed Tickers": len(provider_diag.get("failed", {})),
                }
            ]
            _render_dataframe(pd.DataFrame(provider_rows))

            failed_map = provider_diag.get("failed", {})
            if failed_map:
                failed_df = pd.DataFrame(
                    [{"Ticker": k, "Reason": v} for k, v in failed_map.items()]
                ).sort_values("Ticker")
                st.markdown("##### Provider Failures")
                _render_dataframe(failed_df)

            st.markdown("##### Ticker Data Quality")
            ticker_diag = _ticker_diagnostics(price, div_, st.session_state["start_date"])
            _render_dataframe(
                ticker_diag.style.format(
                    {
                        "Stale (business days)": "{:.0f}",
                        "Price Missing (%)": "{:.2f}",
                        "Dividend Missing (%)": "{:.2f}",
                    },
                    na_rep="",
                )
            )

            st.markdown("##### FX Conversion Status")
            fx_diag = st.session_state.get("fx_diagnostics", {})
            fx_rows = []
            for pair, tickers in fx_diag.get("pair_failures", {}).items():
                fx_rows.append(
                    {
                        "FX Pair": pair,
                        "Status": "FAILED",
                        "Tickers": ", ".join(tickers),
                    }
                )
            if not fx_rows:
                fx_rows = [{"FX Pair": "All attempted pairs", "Status": "OK", "Tickers": ""}]
            _render_dataframe(pd.DataFrame(fx_rows))

            unknown_tickers = fx_diag.get("unknown_currency_tickers", [])
            if unknown_tickers:
                st.warning(
                    "Currency metadata unavailable for: " + ", ".join(unknown_tickers)
                )

            st.markdown("##### Benchmark Status")
            bench_diag = pd.DataFrame(
                [
                    {
                        "Selected Benchmark": benchmark_status.get("selected", index),
                        "Available in Price Data": benchmark_status.get("available", False),
                        "Start Date": str(st.session_state['start_date'].date()) if isinstance(st.session_state.get('start_date'), pd.Timestamp) else str(st.session_state.get('start_date')),
                        "Benchmark Last Date": (
                            benchmark_price.dropna().index.max().date()
                            if isinstance(benchmark_price, pd.Series) and not benchmark_price.dropna().empty
                            else ""
                        ),
                        "Benchmark Missing (%)": (
                            float(pd.to_numeric(benchmark_price, errors="coerce").isna().mean() * 100.0)
                            if isinstance(benchmark_price, pd.Series) and len(benchmark_price) > 0
                            else np.nan
                        ),
                    }
                ]
            )
            _render_dataframe(
                bench_diag.style.format({"Benchmark Missing (%)": "{:.2f}"}, na_rep="")
            )

            action_queue = actions_df.copy() if isinstance(actions_df, pd.DataFrame) else pd.DataFrame()
            if 'upcoming_df' in locals() and isinstance(upcoming_df, pd.DataFrame) and not upcoming_df.empty:
                if "Upcoming Payment Date" in upcoming_df.columns:
                    missing_payment = upcoming_df["Upcoming Payment Date"].isna()
                else:
                    missing_payment = pd.Series(True, index=upcoming_df.index)
                if "Upcoming Dividend ($/share)" in upcoming_df.columns:
                    missing_amount = upcoming_df["Upcoming Dividend ($/share)"].isna()
                else:
                    missing_amount = pd.Series(True, index=upcoming_df.index)
                missing_mask = missing_payment | missing_amount
                missing_rows = upcoming_df[missing_mask].copy()
                if not missing_rows.empty:
                    missing_rows["Event Type"] = "Upcoming Dividend"
                    missing_rows["Event Date"] = pd.to_datetime(
                        missing_rows["Upcoming Ex-Dividend Date"], errors="coerce"
                    ).dt.date
                    missing_rows["Details"] = (
                        "Missing "
                        + np.where(
                            (
                                missing_rows["Upcoming Payment Date"].isna()
                                if "Upcoming Payment Date" in missing_rows.columns
                                else True
                            ),
                            "payment date",
                            "",
                        )
                        + np.where(
                            (
                                missing_rows["Upcoming Dividend ($/share)"].isna()
                                if "Upcoming Dividend ($/share)" in missing_rows.columns
                                else True
                            ),
                            np.where(
                                (
                                    missing_rows["Upcoming Payment Date"].isna()
                                    if "Upcoming Payment Date" in missing_rows.columns
                                    else True
                                ),
                                " & amount",
                                "amount",
                            ),
                            "",
                        )
                    )
                    missing_rows["Action Needed"] = "Verify with broker"
                    missing_rows["Status"] = "Open"
                    queue_cols = ["Ticker", "Event Type", "Event Date", "Details", "Action Needed", "Status"]
                    action_queue = pd.concat(
                        [action_queue, missing_rows[queue_cols]], ignore_index=True
                    )

            st.markdown("##### Corporate Action Queue")
            if action_queue.empty:
                st.info("No action items detected.")
            else:
                if "Event Date" in action_queue.columns:
                    action_queue = action_queue.sort_values(
                        by=["Event Date", "Ticker"], ascending=[False, True], na_position="last"
                    )
                _render_dataframe(action_queue)

        display_calc_details()
            
    if 'portfolio' not in st.session_state: 
        display_readme()
        



def get_and_display_data(file, index, target_currency):
    
    if 'portfolio' in st.session_state:     
        merged_portfolio = get_data(file=file, index=index)
        if process_data(merged_portfolio, target_currency=target_currency, selected_index=index):
            display_data()


# Get index and csv file
with st.sidebar:
    default_index_symbol = indices[1].split(":")[0] if len(indices) > 1 else "^GSPC"
    if "active_benchmark" not in st.session_state:
        st.session_state["active_benchmark"] = default_index_symbol

    # Select a stock index
    index_select = st.selectbox(':chart_with_upwards_trend: Enter the stock index to compare to', 
                                indices,
                                key='index',
                                index=1,
                                help="""Select a stock index to benchmark the portfolio against. 
                                Choose \'Enter Manually\' to manually input an index or stock ticker.
                                \nNote: Indexes generally only reflect the price change of the 
                                underlying stocks and don\'t include dividend data, 
                                whereas stocks may return a dividend.
                                If dividend data is available then this will be used when 
                                calculating the 'Total return' of the benchmark, otherwise the
                                Total return will be the same as Price return""")
    
    if index_select == 'Enter manually':
        manual_index = st.text_input('Input stock ticker', key='manual_index_input')
        manual_index = (manual_index or "").strip().upper()
        if manual_index:
            st.session_state["active_benchmark"] = manual_index
        index = st.session_state.get("active_benchmark", default_index_symbol)
    else:
        # Extract the ticker from the string
        index = index_select.split(':')[0].strip()
        st.session_state["active_benchmark"] = index
        
    base_currency = st.selectbox(':dollar: Select Base Currency', 
                                 currencies, 
                                 index=1,
                                 key='currency',
                                 help='Select the base currency for the portfolio') 
    
    if base_currency == 'Enter manually':
        manual_currency = st.text_input('Input currency code', key='manual_currency_input')
        manual_currency = (manual_currency or "").strip().upper()
        if manual_currency:
            st.session_state["active_base_currency"] = manual_currency
        base_currency = st.session_state.get("active_base_currency", "AUD")
    else:
        # Extract the ticker from the string
        base_currency = base_currency.split(':')[0].strip()
        st.session_state["active_base_currency"] = base_currency
                         
    #st.session_state['index'] = index
    file = st.file_uploader(':open_file_folder: Select the stock portfolio data in csv format', 
                            type='csv',
                            help='Leave blank to use a sample portfolio')   
    
    if file is not None:
        button = st.button('Get share price data', type="primary")
    else:
        try:
            # Get list of csv files in 'default portfolio' directory
            files = os.listdir(os.path.join(os.getcwd(), 'default portfolio'))
            csv_files = sorted([os.path.join(os.getcwd(), 'default portfolio', f) 
                                for f in files if f.endswith('.csv')], 
                                key=os.path.getmtime)
            # Latest csv file
            file = csv_files[-1]
            st.success('Default portfolio located:  \n{:s}   \nClick \'Browse Files\' to load another'.format(os.path.split(file)[1]))
            button = st.button('Get share price data', type="primary")
        except (FileNotFoundError, OSError, IndexError):
            if os.path.exists('sample_portfolio.csv'):   
                file = 'sample_portfolio.csv'
                st.success('Sample portfolio loaded  \nClick \'Browse Files\' to load another')
                button = st.button('Get share price data', type="primary")
            else:
                st.info('Please select a csv file to continue', icon="ℹ️")  
                button = None
 
                     
    if 'portfolio' in st.session_state:
        try:
            _ = st.session_state.pop("reset_start_date_input", False)
            portfolio_version = st.session_state.get("portfolio_version", 0)
            start_date_key = f"start_date_input_{portfolio_version}"
            min_ts = pd.Timestamp(st.session_state['portfolio'].index[0])
            max_ts = pd.Timestamp(
                st.session_state['portfolio'].index[-2]
                if len(st.session_state['portfolio'].index) > 1
                else st.session_state['portfolio'].index[-1]
            )
            default_start_ts = pd.Timestamp(st.session_state.get('start_date', min_ts))
            if default_start_ts < min_ts:
                default_start_ts = min_ts
            if default_start_ts > max_ts:
                default_start_ts = max_ts
            selected_date = st.date_input(
                ':date: Select start date',
                min_value=min_ts.date(),
                max_value=max_ts.date(),
                value=default_start_ts.date(),
                key=start_date_key,
            )
            st.session_state['start_date'] = pd.Timestamp(selected_date)
        except Exception as exc:
            st.warning(f"Start-date control unavailable for current session data ({type(exc).__name__}).")
        

# If button clicked, refresh market data into session state.
if button:
    previous_portfolio = st.session_state.get("portfolio")
    previous_version = st.session_state.get("portfolio_version", 0)
    previous_loaded_benchmark = st.session_state.get("loaded_benchmark")
    try:
        merged_portfolio = get_data(file=file, index=index)
        load_ok = process_data(
            merged_portfolio=merged_portfolio,
            target_currency=base_currency,
            selected_index=index,
        )
        if not load_ok:
            if previous_portfolio is not None:
                st.session_state["portfolio"] = previous_portfolio
                st.session_state["portfolio_version"] = previous_version
                if previous_loaded_benchmark is not None:
                    st.session_state["loaded_benchmark"] = previous_loaded_benchmark
                st.warning("Refresh failed. Showing last successfully loaded portfolio.")
        else:
            # Rebuild sidebar widgets (especially date_input bounds/value) from new portfolio state.
            st.rerun()
    except Exception as exc:
        st.error(f"Refresh failed ({type(exc).__name__}: {exc})")
        if previous_portfolio is not None:
            st.session_state["portfolio"] = previous_portfolio
            st.session_state["portfolio_version"] = previous_version
            if previous_loaded_benchmark is not None:
                st.session_state["loaded_benchmark"] = previous_loaded_benchmark
            st.warning("Showing last successfully loaded portfolio.")

# Always render portfolio view when already loaded in session state.
if 'portfolio' in st.session_state:
    try:
        display_data()
    except Exception as exc:
        st.error(f"Render failed ({type(exc).__name__}: {exc})")
        st.warning("The previous data remains loaded. Try changing inputs and reloading share price data.")
else:
    display_readme()
