import share_tracking as share
import graphs as graph
import streamlit as st
import os
import pandas as pd
import data_provider as dp
import warnings
import re
from collections import defaultdict

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
    return True


def display_calc_details():
    with st.expander(":question: Calculation  \ndetails", expanded=False):
        st.markdown('Some of the following metrics are used to characterise the portfolio:')
        st.markdown('1. **Price Return**')
        st.markdown('Price return is the % return based on share price appreciation only')
        st.markdown('1. **Total Return**')
        st.markdown('Total return includes share price appreciation plus dividend income')
        st.markdown('3. **Basic return**')
        st.markdown('The basic rate of return takes the gain for the portfolio and divides by the (original) investment amount')
        st.markdown('Cash flows are taken into account by assuming they occurred at the beginning of the investment period')
        st.markdown('4. **Time-weighted-return**')
        st.markdown('A time-weighted return attempts to minimize or altogether remove the effects of interim cash flows.')
        st.markdown('Cash flows are weighted according to the amount of time they have been part of the portfolio')
        st.markdown('5. **Annualised returns**')
        st.markdown('An annualized total return is the geometric average amount of money earned by an investment each')
        st.markdown('year over a given time period. The annualized return formula is calculated as a geometric average')
        st.markdown('to show what an investor would earn over a period of time if the annual return was compounded.')
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
        
        # Extract variables for performance calculations
        val, cash_flows, price, accum, shares, div, div_ = share.extract_parameters(st.session_state['portfolio'])
    
        summary_basic = share.stock_summary(st.session_state['portfolio'], index, 
                                      date=st.session_state['start_date'],
                                      calc_method='basic')   
        
        summary_total = share.stock_summary(st.session_state['portfolio'], index, 
                                      date=st.session_state['start_date'],
                                      calc_method='total')   
        
        
        
        #if 'calc_option' not in st.session_state:
        #    st.session_state['calc_option'] = "Basic return"
        
        #calc_option = st.radio(
        #    "Select calculation method",
        #    ["Basic return", 
        #     "Total return"],
        #    index=["Basic return", "Total return"].index(st.session_state['calc_option']),
        #    captions = ["Return based on share price change only", 
        #                "Return including share price change plus dividend income"])

        #st.session_state['calc_option'] = calc_option
        
        #if calc_option == "Basic return":
        #    st.session_state['calc_method'] = 'basic'
        #    st.session_state['div'] = None
        #else:
        #    st.session_state['calc_method'] = 'total'
        #    st.session_state['div'] = div 
        #    st.session_state['portfolio'] = st.session_state['portfolio'] 
        
        # Generate figures
        fig1 = graph.plot_portfolio_gain_plotly(val, cash_flows, price[index],
                                                div=div,
                                                index_div=div_[index],
                                                date=st.session_state['start_date'],
                                                calc_method='basic')
        fig2 = graph.plot_portfolio_gain_plotly(val, cash_flows, price[index],
                                                div=div,
                                                index_div=div_[index],
                                                date=st.session_state['start_date'],
                                                calc_method='total')
        fig3 = graph.plot_stock_gain_plotly(val, cash_flows,
                                            date=st.session_state['start_date'])
        fig4 = graph.plot_stock_holdings_plotly(val, 
                                                date=st.session_state['start_date'])
        fig5 = graph.plot_annualised_return_plotly_(val, cash_flows, price[index], 
                                                    date=st.session_state['start_date'])
        
        tab1, tab2, tab3 = st.tabs(['Portfolio Returns', 'Stock Returns', 'Stock details'])    
        
        with tab1:
            tab_a, tab_b = st.tabs(['Price Return', 'Total Return'])
            with tab_a:
                
                st.plotly_chart(fig1)
                #col1, col2, _ = st.columns([0.6, 3, 0.6])    
                st.dataframe(summary_basic, use_container_width=True)  
            with tab_b:
                
                st.plotly_chart(fig2)    
                st.dataframe(summary_total, use_container_width=True) 
        
        with tab2:
            st.plotly_chart(fig3)
        
        with tab3:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.plotly_chart(fig4)    
            with col2:    
                st.plotly_chart(fig5)

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
 
                     
# If button then extract the data
if button:
    merged_portfolio = get_data(file=file, index=index)
    if process_data(merged_portfolio=merged_portfolio, target_currency=base_currency):
        display_data()
        
# Show a readme if portfolio not extracted
if 'portfolio' not in st.session_state: 
    
    display_readme()
