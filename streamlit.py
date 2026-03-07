import share_tracking as share
import graphs as graph
import streamlit as st
import os
import pandas as pd
import data_provider as dp
import warnings
import re
from collections import defaultdict
import seaborn as sns

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
    
    return merged_portfolio
            

def process_data(merged_portfolio, target_currency):
    
    # Perform initial processing of portfolio data
    try:
        portfolio = share.process_data(merged_portfolio)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", RuntimeWarning)
            portfolio = share.convert_currency(portfolio, target_currency=target_currency)
    except ValueError as exc:
        st.error(str(exc))
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

    st.session_state['portfolio'] = portfolio
    st.session_state["portfolio_version"] = st.session_state.get("portfolio_version", 0) + 1
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
    

def display_data():
    
    if 'portfolio' in st.session_state:     
        
        st.image(os.path.join('screenshots','banner.png'))
        
        #st.session_state['display'] = True
        with st.sidebar:
            max_date = (
                st.session_state['portfolio'].index[-2]
                if len(st.session_state['portfolio'].index) > 1
                else st.session_state['portfolio'].index[-1]
            )
            start_date = st.date_input(':date: Select start date', 
                                        min_value = st.session_state['portfolio'].index[0],
                                        max_value = max_date,
                                        value = st.session_state['portfolio'].index[0],
                                        on_change=display_data)
            st.session_state['start_date'] = start_date

        portfolio_version = st.session_state.get("portfolio_version", 0)
        render_key = (
            portfolio_version,
            str(st.session_state['start_date']),
            index,
        )
        if st.session_state.get("render_cache_key") != render_key:
            # Extract variables for performance calculations
            val, cash_flows, price, accum, shares, div, div_ = share.extract_parameters(st.session_state['portfolio'])
            benchmark_available = index in price.columns
            benchmark_price = price[index] if benchmark_available else pd.Series(1.0, index=price.index, name=index)
            benchmark_div = div_[index] if benchmark_available and index in div_.columns else pd.Series(0.0, index=price.index, name=index)

            if not benchmark_available:
                st.warning(
                    f"Benchmark ticker '{index}' was not found in downloaded price data. "
                    "Benchmark comparisons are temporarily disabled for this render."
                )

            summary_basic = share.stock_summary(
                st.session_state['portfolio'],
                index,
                date=st.session_state['start_date'],
                calc_method='basic',
            )
            summary_total = share.stock_summary(
                st.session_state['portfolio'],
                index,
                date=st.session_state['start_date'],
                calc_method='total',
            )

            fig1 = graph.plot_portfolio_gain_plotly(
                val, cash_flows, benchmark_price,
                div=div, index_div=benchmark_div,
                date=st.session_state['start_date'],
                calc_method='basic',
            )
            fig2 = graph.plot_portfolio_gain_plotly(
                val, cash_flows, benchmark_price,
                div=div, index_div=benchmark_div,
                date=st.session_state['start_date'],
                calc_method='total',
            )
            fig3 = graph.plot_stock_gain_plotly(
                val, cash_flows, date=st.session_state['start_date']
            )
            fig4 = graph.plot_stock_holdings_plotly(
                val, date=st.session_state['start_date']
            )
            fig5 = graph.plot_annualised_return_plotly_(
                val, cash_flows, benchmark_price, date=st.session_state['start_date']
            )

            st.session_state["render_cache"] = {
                "val": val,
                "cash_flows": cash_flows,
                "price": price,
                "accum": accum,
                "shares": shares,
                "div": div,
                "div_": div_,
                "summary_basic": summary_basic,
                "summary_total": summary_total,
                "fig1": fig1,
                "fig2": fig2,
                "fig3": fig3,
                "fig4": fig4,
                "fig5": fig5,
                "scope_figs": {},
            }
            st.session_state["render_cache_key"] = render_key

        cache = st.session_state["render_cache"]
        val = cache["val"]
        cash_flows = cache["cash_flows"]
        price = cache["price"]
        div = cache["div"]
        div_ = cache["div_"]
        fig1 = cache["fig1"]
        fig2 = cache["fig2"]
        fig3 = cache["fig3"]
        fig4 = cache["fig4"]
        fig5 = cache["fig5"]
        summary_basic = cache["summary_basic"]
        summary_total = cache["summary_total"]
        
        tab1, tab2, tab3, tab4 = st.tabs(['Portfolio Returns', 'Stock Returns', 'Stock details', 'Dividend Metrics'])    
        
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
                scope_key = (chart_scope, str(st.session_state['start_date']), index)
                scope_figs = cache.get("scope_figs", {})
                if scope_key not in scope_figs:
                    val_scope = val[[chart_scope]]
                    cf_scope = cash_flows[[chart_scope]]
                    div_scope = div[[chart_scope]] if chart_scope in div.columns else pd.DataFrame(
                        {chart_scope: 0.0}, index=val_scope.index
                    )
                    benchmark_price = (
                        price[index] if index in price.columns else pd.Series(1.0, index=price.index, name=index)
                    )
                    benchmark_div = (
                        div_[index] if index in div_.columns else pd.Series(0.0, index=price.index, name=index)
                    )
                    scope_figs[scope_key] = {
                        "basic": graph.plot_portfolio_gain_plotly(
                            val_scope,
                            cf_scope,
                            benchmark_price,
                            div=div_scope,
                            index_div=benchmark_div,
                            date=st.session_state['start_date'],
                            calc_method='basic',
                        ),
                        "total": graph.plot_portfolio_gain_plotly(
                            val_scope,
                            cf_scope,
                            benchmark_price,
                            div=div_scope,
                            index_div=benchmark_div,
                            date=st.session_state['start_date'],
                            calc_method='total',
                        ),
                    }
                    cache["scope_figs"] = scope_figs
                scope_fig_basic = scope_figs[scope_key]["basic"]
                scope_fig_total = scope_figs[scope_key]["total"]

            if show_total_return:
                st.plotly_chart(scope_fig_total)
                st.dataframe(summary_total, use_container_width=True)
            else:
                st.plotly_chart(scope_fig_basic)
                st.dataframe(summary_basic, use_container_width=True)
        
        with tab2:
            st.plotly_chart(fig3)
        
        with tab3:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.plotly_chart(fig4)    
            with col2:    
                st.plotly_chart(fig5)

        with tab4:
            div_cash = div.loc[st.session_state['start_date']:].fillna(0)
            cf_sel = cash_flows.loc[st.session_state['start_date']:].fillna(0)
            cum_div = div_cash.cumsum()

            if div_cash.empty:
                st.info("No dividend data available for the selected period.")
            else:
                col_cum_div = "Cumulative Dividends ($)"
                col_ttm_div = "Trailing 12M Dividends ($)"
                col_ttm_yoc = "TTM Yield on Cost (%)"
                col_life_yoc = "Lifetime Div/Cost (%)"

                ttm_cutoff = div_cash.index.max() - pd.Timedelta(days=365)
                ttm_div = div_cash.loc[ttm_cutoff:].sum()
                invested = cf_sel.clip(lower=0).sum()
                yield_on_cost_ttm = (ttm_div / invested.replace(0, pd.NA) * 100).fillna(0)
                lifetime_div_to_cost = (
                    cum_div.iloc[-1] / invested.replace(0, pd.NA) * 100
                ).fillna(0)

                div_summary = pd.DataFrame(
                    {
                        col_cum_div: cum_div.iloc[-1],
                        col_ttm_div: ttm_div,
                        col_ttm_yoc: yield_on_cost_ttm,
                        col_life_yoc: lifetime_div_to_cost,
                    }
                ).sort_index()
                div_summary.loc["TOTAL"] = [
                    div_summary[col_cum_div].sum(),
                    div_summary[col_ttm_div].sum(),
                    (ttm_div.sum() / max(invested.sum(), 1e-9)) * 100,
                    (cum_div.iloc[-1].sum() / max(invested.sum(), 1e-9)) * 100,
                ]

                styled_div_summary = (
                    div_summary.style.format(
                        {
                            col_cum_div: "{:.2f}",
                            col_ttm_div: "{:.2f}",
                            col_ttm_yoc: "{:.2f}",
                            col_life_yoc: "{:.2f}",
                        }
                    )
                    .background_gradient(
                        cmap=sns.diverging_palette(20, 145, s=60, as_cmap=True),
                        vmin=-10,
                        vmax=10,
                        subset=[
                            col_ttm_yoc,
                            col_life_yoc,
                        ],
                    )
                )
                st.dataframe(styled_div_summary, use_container_width=True)

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
                        div_cash, selection=div_selection
                    )
                except Exception as exc:
                    st.error(
                        f"Dividend chart render failed for selection '{div_selection}': "
                        f"{type(exc).__name__}: {exc}"
                    )
                    fig_div_cum, fig_div_annual = graph.plot_dividend_metrics_plotly(
                        div_cash, selection="TOTAL"
                    )

                c1, c2 = st.columns(2)
                with c1:
                    st.plotly_chart(fig_div_cum, use_container_width=True)
                with c2:
                    st.plotly_chart(fig_div_annual, use_container_width=True)

        display_calc_details()
            
    if 'portfolio' not in st.session_state: 
        display_readme()
        



def get_and_display_data(file, index, target_currency):
    
    if 'portfolio' in st.session_state:     
        merged_portfolio = get_data(file=file, index=index)
        if process_data(merged_portfolio, target_currency=target_currency):
            display_data()


# Get index and csv file
with st.sidebar:
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
        index = st.text_input('Input stock ticker')    
    else:
        # Extract the ticker from the string
        index = index_select.split(':')[0]   
        
    base_currency = st.selectbox(':dollar: Select Base Currency', 
                                 currencies, 
                                 index=1,
                                 key='currency',
                                 help='Select the base currency for the portfolio') 
    
    if base_currency == 'Enter manually':
        base_currency = st.text_input('Input stock ticker')    
    else:
        # Extract the ticker from the string
        base_currency = base_currency.split(':')[0]
                         
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
 
                     
# If button clicked, refresh market data into session state.
if button:
    merged_portfolio = get_data(file=file, index=index)
    process_data(merged_portfolio=merged_portfolio, target_currency=base_currency)

# Always render portfolio view when already loaded in session state.
if 'portfolio' in st.session_state:
    display_data()
else:
    display_readme()
