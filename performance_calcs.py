import numpy as np
import pandas as pd


def average_price(cash_flows, shares, date=None):
    '''
    Calculate average buy price based on number of shares accumulated and cash flows into the 
    portfolio. Sales of shares are not included in the calculation.

    Parameters
    ----------
    cash_flows : pandas.DataFrame or pandas.Series
        Dollar value of cash flows into or out of the portfolio. Data should be time series indexed.
        Each column is assummed to be a different stock in the portfolio
    shares : pandas.DataFrame or pandas.Series
        Number of shares bought or sold. A negative number indicates a sale. Data should be time
        series indexed and each column is assummed to be a different stock in the portfolio.
    date : string, optional
        Optional date string to pass to the Datetime index set the start date for the portfolio. 
        Full or partial string can be provided eg '20210415' or '2018'. The default is None.

    Returns
    -------
    avg_price : pandas.DataFrame or pandas.Series
        average stock buy price calculated for each stock and for each date in the time series 
        index.

    '''
    # Truncate based on date argument
    cash_flows = cash_flows.loc[date:]
    shares = shares.loc[date:]
    
    # Sum of positive cash flows / shares held
    # the shares >= 0 mask is used to allow cost base adjustments to be included. I.e. if the 
    # cost base is reduced but the number of shares is unchanged, the average price will be 
    # adjusted downwards
    avg_price = (cash_flows[cash_flows != 0][shares >= 0].cumsum() 
                 / shares[shares >= 0].cumsum()).ffill()
    
    return avg_price


def basic_return(val, cash_flows, date=None, use_initial_CF=False):
    '''
    basic return = (V1 - V0 - CF) / (V0 + CF) 
    where, 
    V0 = starting value 
    V1 = ending value
    CF = sum of cash flows into and out of the portfolio
    assumes cash flows were at the beginning of the performance period, therefore the cash flows 
    'earned' part of the gains
    
    https://www.kitces.com/blog/twr-dwr-irr-calculations-performance-reporting-software-methodology-gips-compliance/
    
    Parameters
    ----------
    val : pandas.DataFrame or pandas.Series
        Cumulative dollar value of each stock holdings. Data should be time series indexed.
        Each column is assummed to be a different stock in the portfolio.
    cash_flows : pandas.DataFrame or pandas.Series
        Dollar value of cash flows into or out of the portfolio. Data should be time series indexed.
        Each column is assummed to be a different stock in the portfolio
    date : string, optional
        Optional date string to pass to the Datetime index set the start date for the portfolio. 
        Full or partial string can be provided eg '20210415' or '2018'. The default is None.
    use_initial_CF : bool, optional
        Use the first row of cash_flow as the initial portfolio value instead of the first row
        of val. If the first date in the dataframe represents the first purchase date of the 
        portfolio then use_initial_CF should be set to True to give the correct cost base. 
        The default is False.

    Returns
    -------
    basic_return : pandas.DataFrame or pandas.Series
        Basic return (%) calculated for each stock and for each date in the time series 
        index.
    '''
    # TODO: Allow calc with zero cash flows - need to use first non-zero val in val col
    #pd.Series(0, index=price[index].index,name=price[index].name)
    
    # Truncate based on date argument
    val = val.loc[date:]
    cash_flows = cash_flows.loc[date:]
    
    
    if use_initial_CF == False:
        # V0 = value at time zero
        V0 = val.iloc[0]
    else:
        # V0 = cash flows at index zero
        V0 = cash_flows.iloc[0]
    
    basic_ret = (((val - V0 - cash_flows.iloc[1:].cumsum()) / (V0 + cash_flows.iloc[1:].cumsum()))
                 .fillna(0)
                 .replace(-1, 0))
         
    return basic_ret


def basic_return_annualised(val, cash_flows, date=None, use_initial_CF=False):
    '''
    Annualized Return = (1 + basic_return())**(years held) - 1
    
    https://www.investopedia.com/terms/a/annualized-total-return.asp
    
    Parameters
    ----------
    val : pandas.DataFrame or pandas.Series
        Cumulative dollar value of each stock holdings. Data should be time series indexed.
        Each column is assummed to be a different stock in the portfolio.
    cash_flows : pandas.DataFrame or pandas.Series
        Dollar value of cash flows into or out of the portfolio. Data should be time series indexed.
        Each column is assummed to be a different stock in the portfolio
    date : string, optional
        Optional date string to pass to the Datetime index set the start date for the portfolio. 
        Full or partial string can be provided eg '20210415' or '2018'. The default is None.
    use_initial_CF : bool, optional
        Use the first row of cash_flow as the initial portfolio value instead of the first row
        of val. If the first date in the dataframe represents the first purchase date of the 
        portfolio then use_initial_CF should be set to True to give the correct cost base. 
        The default is False.

    Returns
    -------
    basic_ret : pandas.DataFrame or pandas.Series
        Annualised Basic return (%) calculated for each stock and for each date in the time series 
        index.
    '''
    #TODO: Add handling of datatypes other than DataFrame or pd.Series
    
    # Truncate based on date argument
    val = val.loc[date:]
    cash_flows = cash_flows.loc[date:]
    
    # Find the first non-zero row of each col - which becomes the start date for calculating the
    # num_years. Set num_years to 1 if (val==0).all() to avoid divide by zero error
    # Assume 261 business days in a calender year
    if isinstance(val, pd.DataFrame):
        num_years = val.apply(lambda x: (pd.Series(x.loc[x.ne(0).idxmax():].reset_index().index.values, 
                                                   index=x.loc[x.ne(0).idxmax():].index) / 261) 
                              if not (x == 0).all() 
                              else pd.Series(1, index=x.index)) 
    
    if isinstance(val, pd.Series):
        num_years = ((pd.Series(val.loc[val.ne(0).idxmax():].reset_index().index.values, 
                              index=val.loc[val.ne(0).idxmax():].index) / 261) 
                          if not (val == 0).all() 
                          else pd.Series(1, index=val.index))
    
    basic_ret_ann = np.power(basic_return(val, cash_flows, use_initial_CF=use_initial_CF) + 1, 
                             1 / num_years) - 1
    
    return basic_ret_ann    


def daily_pct_gain(price):
    '''
    Percentage change for each row in the Dataframe/Series.

    Parameters
    ----------
    price : pandas.DataFrame or pandas.Series
        Share price, typically time series indexed

    Returns
    -------
    pct_change: pandas.DataFrame or pandas.Series
        percentage change.

    '''
    
    return price.pct_change()


def daily_portfolio_pct_gain(val, price):
    '''
    Calculates time-series incremented (typically daily) percentage gain of a stock portfolio
    based on the value of its component stock holdings and their price change over time.     

    Parameters
    ----------
    val : pandas.DataFrame or pandas.Series
        Cumulative dollar value of each stock holdings. Data should be time series indexed.
        Each column is assummed to be a different stock in the portfolio.
    price : pandas.DataFrame or pandas.Series
        Share price, time series indexed
    
    Returns
    -------
    gain : pandas.Series
        Percentage gain, time series indexed

    '''
    
    gain = ((val.shift(1) * price.pct_change()).sum(axis=1) / val.shift(1).sum(axis=1)
            .fillna(0))
    
    return gain   

    
def time_weighted_return(val, cash_flows, date=None, use_initial_CF=False):
    '''
    Calculates the time-weighted return based on the Modified-Dietz formula.
    time weighted return = (V1 - V0 - CF) / (V0 + CF(t)) 
    where, 
    V0 = starting value 
    V1 = ending value
    CF = sum of cash flows into and out of the portfolio
    CF(t) are cash flows weighted for time in the portfolio
    
    https://www.kitces.com/blog/twr-dwr-irr-calculations-performance-reporting-software-methodology-gips-compliance/
    
    Parameters
    ----------
    val : pandas.DataFrame or pandas.Series
        Cumulative dollar value of each stock holdings. Data should be time series indexed.
        Each column is assummed to be a different stock in the portfolio.
    cash_flows : pandas.DataFrame or pandas.Series
        Dollar value of cash flows into or out of the portfolio. Data should be time series indexed.
        Each column is assummed to be a different stock in the portfolio
    date : string, optional
        Optional date string to pass to the Datetime index set the start date for the portfolio. 
        Full or partial string can be provided eg '20210415' or '2018'. The default is None.
    use_initial_CF : bool, optional
        Use the first row of cash_flow as the initial portfolio value instead of the first row
        of val. If the first date in the dataframe represents the first purchase date of the 
        portfolio then use_initial_CF should be set to True to give the correct cost base. 
        The default is False.

    Returns
    -------
    time_weighted_return : pandas.DataFrame or pandas.Series
        Time weighted return (%) calculated for each stock and for each date in the time series 
        index.
    '''
    # MDR on a per stock basis. 
    # start from first non-zero accumulation    
    
    # Truncate based on date argument
    val = val.loc[date:]
    cash_flows = cash_flows.loc[date:]    
    
    # Convert Pandas Series to dataframe
    if not isinstance(val, pd.DataFrame):
        val = pd.DataFrame(val)
    if not isinstance(cash_flows, pd.DataFrame):
        cash_flows = pd.DataFrame(cash_flows)
    
    MDR = pd.DataFrame([])
    for column in val:
        
        vcol = val[column]
        ccol = cash_flows[column]
        
        if (vcol == 0).all():
            MDR_individual = pd.Series(0, index=vcol.index, name=vcol.name)
       
        else:
            # Intial value of stock holding    
            initial_val = vcol[0]
            
            # Start from first non-zero row
            start_index = val[vcol!=0].index[0]
            vcol = vcol.loc[start_index:]        
            ccol = ccol.loc[start_index:]        
            
            # Only use the val column for intial val/cost base if use_initial_CF == False
            # and the first row is non-zero (i.e. there are no holdings at the start date)
            # Otherwise the first cash flow can be used as the intial portfolio val (V0)
            # This matches the methodology used for Basic Return calc.
            #if use_initial_CF == False or initial_val == 0:
            #    V0 = vcol.iloc[0]
            if use_initial_CF != False or initial_val == 0:
                V0 = ccol.iloc[0]
            else:
                V0 = vcol.iloc[0]
            #if use_initial_CF == False and vcol[0] != 0:
            #    V0 = vcol.iloc[0]
            #else:
            #    V0 = ccol.iloc[0]
                
            CF_sum = ccol.iloc[1:].cumsum()
            t = vcol.reset_index().index.values
            CF_time = (-1 * (ccol.iloc[1:] * t[1:]).cumsum() / t[1:] + ccol.iloc[1:].cumsum())
            MDR_individual = (((vcol - V0 - CF_sum) / (V0 + CF_time))
                              .fillna(0)
                              .replace(-1, 0))
            
            # Set return to 0 if val of the holding = 0
            MDR_individual[vcol==0] = 0
    
        MDR = pd.merge(MDR, MDR_individual, how='outer', left_index=True, right_index=True)
        
    return MDR


def time_weighted_return_annualised(val, cash_flows, date=None, use_initial_CF=False):
    '''
    Annualized Return = (1 + time_weighted_return())**(years held) - 1
    
    https://www.investopedia.com/terms/a/annualized-total-return.asp
    
    Parameters
    ----------
    val : pandas.DataFrame or pandas.Series
        Cumulative dollar value of each stock holdings. Data should be time series indexed.
        Each column is assummed to be a different stock in the portfolio.
    cash_flows : pandas.DataFrame or pandas.Series
        Dollar value of cash flows into or out of the portfolio. Data should be time series indexed.
        Each column is assummed to be a different stock in the portfolio
    date : string, optional
        Optional date string to pass to the Datetime index set the start date for the portfolio. 
        Full or partial string can be provided eg '20210415' or '2018'. The default is None.
    use_initial_CF : bool, optional
        Use the first row of cash_flow as the initial portfolio value instead of the first row
        of val. If the first date in the dataframe represents the first purchase date of the 
        portfolio then use_initial_CF should be set to True to give the correct cost base. 
        The default is False.

    Returns
    -------
    MDR_ann : pandas.DataFrame or pandas.Series
        Annualised time weighted (Modified-Dietz) return (%) calculated for each stock and for 
        each date in the time series index.
    '''
    # MDR on a per stock basis. 
    # start from first non-zero accumulation    
    
    # Truncate based on date argument
    val = val.loc[date:]
    cash_flows = cash_flows.loc[date:]
    
    # Convert Pandas Series to dataframe for num_years calculation
    if not isinstance(val, pd.DataFrame):
        val = pd.DataFrame(val)
    if not isinstance(cash_flows, pd.DataFrame):
        cash_flows = pd.DataFrame(cash_flows)        
    
    # Find the first non-zero row of each col - which becomes the start date for calculating the
    # num_years. Set num_years to 1 if (val==0).all() to avoid divide by zero error
    # Assume 261 business days in a calender year
    num_years = val.apply(lambda x: (pd.Series(x.loc[x.ne(0).idxmax():].reset_index().index.values, 
                                                   index=x.loc[x.ne(0).idxmax():].index) / 261) 
                              if not (x == 0).all() 
                              else pd.Series(1, index=x.index)) 
       
    MDR_ann = np.power(time_weighted_return(val, cash_flows) + 1, 1 / num_years) - 1
        
    return MDR_ann