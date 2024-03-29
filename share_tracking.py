import performance_calcs as calc
import pandas as pd
import numpy as np
import seaborn as sns
#from datetime import datetime
import sys
import yfinance as yf

# TODO:
# Add brokerage column into cost base calculation
# Allow specification of a subset of dates when plotting portfolio performance
# calc_stockdata - change time(t) to be days, not business days
# stock_summary - check whether supplied date argument is a business day
# Dividend metrics
# csv file columns case insensitive
# allow for multiple sales or purcahses in a single day
# add dollar weighted return calculation
# Add first purchase date in stock_summary()
# Print time period when displaying summary table and summary plots
# total return - last value before all shares sold
# Date to US format
# fix average price calc for reduced data range
# fix graph legend if single stock holding
# add support for multiple currencies
# add dividends
# Add automatic control of stock splits

###################################################################################################
def get_userdata(filename):
    '''
    Reads a csv file of the users stock portfolio and loads into a dataframe. 
    Column headers should be as follows:
        'Company' : Company stock ticker
        'Shares' : Number of shares bought or sold (negative number = sold)
        'Date' : Date in DD/MM/YYYY format
        'Price' : Price paid/received per share
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
    '''
       
    # Get buy/sell data for shares from the .csv file
    #imp_a = pd.read_csv(filename)
    
    import_a = pd.read_csv(filename, index_col = ['Company', 'Date'])
                
    # Drop non-required columns, drop NaN rows, drop NaN rows in index, Unstack 'Company' col
    import_a = (import_a.drop(import_a.columns.difference(['Shares','Price', 'Adjustments']), axis=1)
                .dropna(how='all'))   
    import_a = import_a.loc[import_a.index.dropna()].unstack(level=0)                
    
    # Convert index to Datetime
    import_a.index = pd.to_datetime(import_a.index, format='%d/%m/%Y')
    import_a = import_a.sort_index()
    
    # Set column names
    import_a.columns.rename(['Params', 'Company'], inplace=True)
        
    # Check whether all dates in portfolio are business days. Data may not be captured if not. 
    for i in import_a.index:
        if i not in import_a.sort_index().asfreq(freq='B').index:
            print('\nWARNING: date {} is not a business day. All dates should be '
                  'business days for correct data capture'.format(i))
            sys.exit()    
    
    return import_a    

  
     
def merge_pricedata(portfolio, index):
    '''
    Reads portfolio dataframe generated by get_stockdata(), and extracts a list of stock tickers in
    the portfolio. Use API to get time series stock price data for the stocks listed and merge price 
    data with the portfolio dataframe. The returned dataframe is indexed as a time series, with 
    business day frequency.


    Parameters
    ----------
    portfolio : pandas.DataFrame
        portfolio dataframe generated by get_stockdata().
    index : string
        stock ticker to compare portfolio performance. Typically this would be the ticker
        of an ETF that tracks an index, eg "SPY" which tracks the S&P 500 index.

    Returns
    -------
    import_a : pandas.DataFrame
        Time series dataframe containing stock purchase and sale information, merged with stock
        price data over the time frame convered by the portfolio

    '''
    
    # Portfolio start and end time for extracting data using API   
    start_date = min(portfolio.index)
    start_time = start_date.strftime("%Y-%m-%d")
    #start_time = int(start_date.timestamp())
    #end_time = datetime.today().replace(second=0, microsecond=0).strftime("%m/%d/%Y")  
    
    # Fetch stock prices using API and merge with trading data 
    inputdata = {}
    print('\nAPI call in progress...\n')
    
    # Extract list of portfolio tickers
    tickers = list(portfolio.columns.levels[1]) + [index]
    for i in tickers:

        # Extract price data using API
        #inputdata = yf.download(i, start=start_time, progress=False)
        inputdata = (yf.Ticker(i).history(start=start_time, auto_adjust=False)
                     .tz_localize(None))
        
        # Convert price data into dataframe
        #cols = pd.MultiIndex.from_arrays([['$'], [i]], names = ['Params', 'Company'])        
        cols = pd.MultiIndex.from_arrays([['$', 'Div'], [i, i]], 
                                         names = ['Params', 'Company'])
        
        #df = pd.DataFrame(inputdata['Close'].values, 
        #                  index=inputdata.index,
        #                  columns=cols)
        
        df = pd.DataFrame(inputdata[['Close', 'Dividends']].values, 
                          index=inputdata.index,
                          columns=cols)
                
                         
        # Merge portfolio and prices dataframes
        portfolio = pd.merge(portfolio, df, how='outer', 
                             left_index=True, right_index=True).drop_duplicates()
        

    print('API call complete\n')
        
    # Set to 'Business day' datetime frequency
    portfolio = portfolio.sort_index().asfreq(freq='B') 
    
    return portfolio



def process_data(merged_portfolio):
    '''
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

    '''    
    # Define IndexSlice for dataframe slicing
    idx = pd.IndexSlice
    
    # Handle Na values in stock prices.
    #merged_portfolio.loc[:, idx['$', :]] = (merged_portfolio.loc[:, idx['$', :]]
    #                                        .fillna(method='ffill')
    #                                        .fillna(0))    
    
    merged_portfolio['$'] = merged_portfolio['$'].fillna(method='ffill').fillna(0)
    
    
    # Fill Na values in Shares and Price and Div column
    merged_portfolio.loc[:, idx[['Shares', 'Price', 'Div'], :]] = (
                                    merged_portfolio.loc[:, idx[['Shares', 'Price', 'Div'], :]].fillna(0))
    #merged_portfolio[['Shares', 'Price', 'Div']] = merged_portfolio[['Shares', 'Price', 'Div']].fillna(0)
    
    
    
    # Accumulated shares  
    Accum = (merged_portfolio['Shares'][~np.isnan(merged_portfolio['Shares'])].cumsum()
                                     .fillna(method='ffill')
                                     .fillna(0))
    Accum.columns = pd.MultiIndex.from_product([['Accum'], Accum.columns], 
                                               names = ['Params', 'Company'])
    
    # Current val of each stock holding
    Val = merged_portfolio['$'] * Accum
    Val.columns = pd.MultiIndex.from_product([['Val'], Val.columns.get_level_values(1)],
                                                 names = ['Params', 'Company'])  
    
    # Cash flows into portfolio
    Buy_amt = ((merged_portfolio['Price'] * merged_portfolio['Shares'])
               .fillna(0))    
    
    
    # Cash flow adjustments due to demerger/acquisition event.
    if 'Adjustments' in merged_portfolio.columns:
        #merged_portfolio.loc[:, idx['Adjustments', :]] = (
        #                                merged_portfolio.loc[:, idx['Adjustments', :]].fillna(0))
        
        merged_portfolio['Adjustments'] = merged_portfolio['Adjustments'].fillna(0)
        
        # Use .loc for Adjustments to maintain the multiindex columns
        Buy_amt = Buy_amt + merged_portfolio.loc[:, idx['Adjustments', :]] * Buy_amt.cumsum()     
        
        # Reset column names
        Buy_amt.columns = pd.MultiIndex.from_product([['Buy_amt'], 
                                                      Buy_amt.columns.get_level_values(1)],
                                                      names = ['Params', 'Company'])    
        
        # Add adjustments into Dividends
        merged_portfolio['Div'] = (merged_portfolio['Div']
                                   + merged_portfolio['Adjustments']
                                   * merged_portfolio['Div'].cumsum()) 
                                   
    else:
        # Reset column names
        Buy_amt.columns = pd.MultiIndex.from_product([['Buy_amt'], Buy_amt.columns],
                                                     names = ['Params', 'Company']) 
    
        
    # Concatenate processed data with original dataframe
    merged_portfolio = pd.concat([merged_portfolio, Buy_amt, Accum, Val], axis=1)
    
    return merged_portfolio
    

def extract_parameters(processed_portfolio):
    '''
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
    '''
    
    val = processed_portfolio['Val']
    cash_flows = processed_portfolio['Buy_amt']
    price = processed_portfolio['$']
    accum = processed_portfolio['Accum']
    shares = processed_portfolio['Shares']
    div = processed_portfolio['Div'] * accum
    
    return val, cash_flows, price, accum, shares, div
    

'''        
        # Average price. Replace inf values (may exist if accum = 0) with 0
        df[col+'_avg_price'] = (df[col + '_buy_amt'][df[col+'_buy_amt']>0].cumsum() / 
                                 df[col+'_n'][df[col+'_n']>0].cumsum())
        df[col+'_avg_price'] = df[col+'_avg_price'].ffill()
        
        if adjustments_exist == True:
            df[col+'_avg_price'] = df[col+'_avg_price'] * (1 + df[col+'_adj'])
    
'''    



###################################################################################################

def stock_summary(cash_flows, shares, price, accum, val, index, date=None, styles=True):
    
    # Test for portfolio of single stock. (iloc[-1].values line will retuen an error)
    '''
    Displays a summary table of portfolio and individual stock metrics
    On a per stock basis:
        Average price
        Current price
        Current holdings
        Current value
        Daily return
        Total return (basic return)
        Annualised return (annualised basic return)
    For the portfolio
        Current value
        Daily return
        Total return (basic return)
        Annualised return (annualised basic return)

    Parameters
    ----------
    dataframe : dataframe
        Dataframe generated by calc_stockdata()..
    stocks : list
        List of stock tickers. Can be a list of all tickers included in the dataframe or a subset.

    Returns
    -------
    di : dataframe
        Summary dataframe.

    '''   

    init_CF = (price.shape == price[date:].shape)
    
    cash_flows = cash_flows[date:]
    shares = shares[date:]
    accum = accum[date:]
    price = price[date:]
    val = val[date:]
    
    #init_CF = (True if date == None else False) 
    
    df = pd.DataFrame()
    df.index.name = 'Company'
    
    # STOCKS SUMMARY
    df['Average Price'] = calc.average_price(cash_flows, shares).iloc[-1]
    df['Current Price'] = price.iloc[-1]
    df['Current Holdings'] = accum.iloc[-1]
    df['Current Value'] = val.iloc[-1]
    df['Daily Return (%)'] = calc.daily_pct_gain(price.drop(labels=index, axis=1)).iloc[-1] * 100
    df.loc[df['Current Holdings'] == 0, 'Daily Return (%)'] = 0
    df['Total Return (%)'] = (calc.basic_return(val, cash_flows, use_initial_CF=init_CF)
                              .iloc[-1].values * 100)
    df['Annualised Return (%)'] = (calc.basic_return_annualised(val, cash_flows, 
                                                                use_initial_CF=init_CF)
                                   .iloc[-1].values * 100)
    df['Time Weighted Return (%)'] = (calc.time_weighted_return(
                                            val, cash_flows, use_initial_CF=init_CF)
                                      .iloc[-1].values * 100)
    df['Annualised Time Weighted Return (%)'] = ((calc.time_weighted_return_annualised(
                                                    val, cash_flows, use_initial_CF=init_CF)
                                                  .iloc[-1].values * 100))
    df = df.sort_index().reset_index()
    #di['Current Holdings'] = di['Current Holdings'].astype(int)
    
    # TOTAL ROW
    end_idx = len(df.index)
    
    df.loc[end_idx, 'Company'] = 'TOTAL'
    df.loc[end_idx, 'Current Value'] = df['Current Value'].sum()
    df.loc[end_idx, 'Daily Return (%)'] = calc.daily_portfolio_pct_gain(val, price).iloc[-1] * 100 
    df.loc[end_idx, 'Total Return (%)'] = calc.basic_return(val.sum(axis=1), cash_flows.sum(axis=1), 
                                                       use_initial_CF=init_CF).iloc[-1] * 100
    df.loc[end_idx, 'Annualised Return (%)'] = calc.basic_return_annualised(val.sum(axis=1), cash_flows.sum(axis=1), 
                                                       use_initial_CF=init_CF).iloc[-1] * 100
    df.loc[end_idx, 'Time Weighted Return (%)'] = (calc.time_weighted_return(val.sum(axis=1),
                                                                             cash_flows.sum(axis=1), 
                                                                             date=None, 
                                                                             use_initial_CF=init_CF)
                                                   .iloc[-1].values * 100)
    df.loc[end_idx, 'Annualised Time Weighted Return (%)'] = (calc.time_weighted_return_annualised(
                                                                        val.sum(axis=1),
                                                                        cash_flows.sum(axis=1), 
                                                                        date=None, 
                                                                        use_initial_CF=init_CF)
                                                              .iloc[-1].values * 100)
    df.loc[len(df.index)] = np.nan    # blank row
    df.loc[len(df.index)-1, 'Company'] = ''
    
    # BENCHMARK SUMMARY
    end_idx = len(df.index)
    df.loc[end_idx, 'Company'] = 'BENCHMARK (' + index + ')'  
    df.loc[end_idx, 'Daily Return (%)'] = calc.daily_pct_gain(price[index]).iloc[-1] * 100
    df.loc[end_idx, 'Total Return (%)'] = (calc.basic_return(price[index], 
                                                       pd.Series(0, index=price[index].index, 
                                                                 name=price[index].name))
                                           .iloc[-1] * 100)  
    df.loc[end_idx, 'Annualised Return (%)'] =  (calc.basic_return_annualised(
                                                price[index], pd.Series(0, index=price[index].index, 
                                                                        name=price[index].name))
                                                 .iloc[-1] * 100)
    df.loc[end_idx, 'Time Weighted Return (%)'] = df.loc[end_idx, 'Total Return (%)']
    df.loc[end_idx, 'Annualised Time Weighted Return (%)'] = df.loc[end_idx, 'Annualised Return (%)']
    
    if styles:     
        # DATAFRAME STYLES
        # Set colormap using Seaborn palette
        cmap = sns.diverging_palette(20, 145, s=60, as_cmap=True)
        
        df = (df.style.format(na_rep='', formatter={'Average Price': "{:.4f}",
                                                    'Current Price': "{:.2f}",
                                                    'Current Holdings': "{:.0f}", 
                                                    'Current Value': "{:.2f}", 
                                                    'Daily Return (%)': "{:.2f}",
                                                    'Total Return (%)': "{:.2f}", 
                                                    'Annualised Return (%)': "{:.2f}",
                                                    'Time Weighted Return (%)': "{:.2f}",
                                                    'Annualised Time Weighted Return (%)': "{:.2f}"})
                      .background_gradient(cmap=cmap, vmin=-2, vmax=2, 
                                           subset=(slice(len(df)-3), 'Daily Return (%)'))
                      .background_gradient(cmap=cmap, vmin=-100, vmax=100, 
                                           subset=(slice(len(df)-3), ['Total Return (%)', 
                                                                      'Time Weighted Return (%)']))
                      .background_gradient(cmap=cmap, vmin=-10, vmax=10, 
                             subset=(slice(len(df)-3), ['Annualised Return (%)',
                                                        'Annualised Time Weighted Return (%)']))
                      .background_gradient(cmap=cmap, vmin=-2, vmax=2, 
                                           subset=(len(df)-1, 'Daily Return (%)'))
                      .background_gradient(cmap=cmap, vmin=-100, vmax=100, 
                                                subset=(len(df)-1, ['Total Return (%)', 
                                                                    'Time Weighted Return (%)']))
                      .background_gradient(cmap=cmap, vmin=-10, vmax=10, 
                                    subset=(len(df)-1, ['Annualised Return (%)',
                                                        'Annualised Time Weighted Return (%)'])))
          
    return df