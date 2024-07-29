import share_tracking as share
import graphs as graph
import streamlit as st
import os
import pandas as pd

# Basic webpage setup
st.set_page_config(
   page_title="Portfolio Tracker",
   layout="wide",
   initial_sidebar_state="expanded",
)

# import stock index data
indices = pd.read_csv('stock_indices.csv')
indices = tuple(indices['Symbol'] + ': ' +indices['Name'])


def get_data():
    
    with st.sidebar:
        with st.spinner('Collecting share price data'):
            user_portfolio = share.get_userdata(file)
            merged_portfolio = share.merge_pricedata(user_portfolio, index)
                                                     
        st.success('Success')
    
    return merged_portfolio
            

def process_data(merged_portfolio):
    
    # Perform initial processing of portfolio data
    portfolio = share.process_data(merged_portfolio)
    st.session_state['portfolio'] = portfolio


def display_calc_details():
    with st.expander(":question: Calculation  \ndetails", expanded=False):
        st.markdown('Some of the following metrics are used to characterise the portfolio:')
        st.markdown('https://www.kitces.com/blog/twr-dwr-irr-calculations-performance-reporting-software-methodology-gips-compliance/')
        st.markdown('1. **Basic return**')
        st.markdown('The basic rate of return takes the gain for the portfolio and divides by the (original) investment amount')
        st.markdown('Cash flows are taken into account by assuming they occurred at the beginning of the investment period')
        st.markdown('2. **Time-weighted-return**')
        st.markdown('A time-weighted return attempts to minimize or altogether remove the effects of interim cash flows.')
        st.markdown('Cash flows are weighted according to the amount of time they have been part of the portfolio')
        st.markdown('3. **Annualised returns**')
        st.markdown('An annualized total return is the geometric average amount of money earned by an investment each')
        st.markdown('year over a given time period. The annualized return formula is calculated as a geometric average')
        st.markdown('to show what an investor would earn over a period of time if the annual return was compounded.')


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
    st.markdown('**Adjustments:** (Optional column) This column allow for a cost base adjustment to be made. Eg, if a company restructure takes place,') 
    st.markdown('a portion of the cost base may be split into a new entity. The number entered into the \'_Adjustments_\' column represents')
    st.markdown('the portion of the cost base that is to be removed. I.e, a value of `-0.1` indicates a 10% reduction in the cost base.')
    

def display_data():
    
    if 'portfolio' in st.session_state:     
        
        st.image(os.path.join('screenshots','banner.png'))
        
        #st.session_state['display'] = True
        with st.sidebar:
            start_date = st.date_input(':date: Select start date', 
                                        min_value = st.session_state['portfolio'].index[0],
                                        max_value = st.session_state['portfolio'].index[-2],
                                        value = st.session_state['portfolio'].index[0],
                                        on_change=display_data)
            st.session_state['start_date'] = start_date
        
        # Extract variables for performance calculations
        val, cash_flows, price, accum, shares, div, div_ = share.extract_parameters(st.session_state['portfolio'])
    
        summary = share.stock_summary(st.session_state['portfolio'], index, 
                                      date=st.session_state['start_date'],
                                      calc_method='basic')   
        
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
        fig2 = graph.plot_stock_gain_plotly(val, cash_flows,
                                            date=st.session_state['start_date'])
        fig3 = graph.plot_stock_holdings_plotly(val, 
                                                date=st.session_state['start_date'])
        fig4 = graph.plot_annualised_return_plotly_(val, cash_flows, price[index], 
                                                    date=st.session_state['start_date'])
        
          
        
        tab1, tab2, tab3 = st.tabs(['Portfolio Gain', "Stock Gain", "Stock details"])    
        
        with tab1:
            st.plotly_chart(fig1)
            col1, col2, _ = st.columns([0.6, 3, 0.6])               
        
        with tab2:
            st.plotly_chart(fig2)
        
        with tab3:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.plotly_chart(fig3)    
            with col2:    
                st.plotly_chart(fig4)
        
        st.dataframe(summary, use_container_width=True)
        
        display_calc_details()
            
    if 'portfolio' not in st.session_state: 
        display_readme()
        



def get_and_display_data():
    
    if 'portfolio' in st.session_state:     
        merged_portfolio = get_data()
        process_data(merged_portfolio)
        display_data()


# Get index and csv file
with st.sidebar:
    
    # Select a stock index
    index_select = st.selectbox(':chart_with_upwards_trend: Enter the stock index to compare to', indices)
    # Extract the ticker from the string
    index = index_select.split(':')[0]
    
    manual = st.checkbox('Input index manually')
    if manual:
        index = st.text_input('Input stock ticker')
    
    
                         
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
        except:
            if os.path.exists('sample_portfolio.csv'):   
                file = 'sample_portfolio.csv'
                st.success('Sample portfolio loaded  \nClick \'Browse Files\' to load another')
                button = st.button('Get share price data', type="primary")
            else:
                st.info('Please select a csv file to continue', icon="ℹ️")  
                button = None
 
                     
# If button then extract the data
if button:
    
    merged_portfolio = get_data()
    process_data(merged_portfolio)
    display_data()
        
# Show a readme if portfolio not extracted
if 'portfolio' not in st.session_state: 
    
    display_readme()


