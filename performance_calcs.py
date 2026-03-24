import numpy as np
import pandas as pd
import numpy_financial as npf


def _resolve_dwr_resample_freq(val, resample_freq, base_rows):
    if resample_freq == "auto":
        num_rows = len(val)
        if isinstance(val, pd.DataFrame):
            num_cols = max(1, val.shape[1])
        else:
            num_cols = 1
        work_units = num_rows * num_cols
        if work_units <= base_rows:
            return "B"
        if work_units <= base_rows * 7:
            return "W-FRI"
        if work_units <= base_rows * 30:
            return "BME"
        return "BQE"
    if resample_freq not in ["W", "M", "Q"]:
        raise ValueError("resample_freq must be 'auto', 'W', 'M', or 'Q'")
    if resample_freq == "W":
        return "W-FRI"
    if resample_freq == "M":
        return "BME"
    return "BQE"

def prepare_data(*args, date=None):
        """
        Helper function
        Truncate data based on date argument and convert Series to DataFrame.
        
        Parameters:
        *args: Variable number of pandas Series or DataFrames
        date: Optional date string to truncate the data
        
        Returns:
        List of prepared DataFrames
        """
        prepared_data = []
        for arg in args:
            # Truncate based on date argument
            if date is not None:
                arg = arg.loc[date:]
            
            # Convert Pandas Series to DataFrame
            if not isinstance(arg, pd.DataFrame):
                arg = pd.DataFrame(arg)
            
            prepared_data.append(arg)
        
        return prepared_data
    

def _elapsed_years_from_first_nonzero(val, periods_per_year=261):
    """
    Compute elapsed years from the first non-zero value.
    Uses a minimum elapsed period of 1/periods_per_year to avoid zero-year exponents.
    """
    if isinstance(val, pd.Series):
        if (val == 0).all():
            return pd.Series(1.0, index=val.index, name=val.name)

        start_index = val[val != 0].index[0]
        elapsed = pd.Series(1.0, index=val.index, name=val.name, dtype=float)
        elapsed_steps = (np.arange(len(val.loc[start_index:])) + 1) / periods_per_year
        elapsed.loc[start_index:] = elapsed_steps
        return elapsed

    if isinstance(val, pd.DataFrame):
        elapsed_df = pd.DataFrame(index=val.index, columns=val.columns, dtype=float)
        for col in val.columns:
            elapsed_df[col] = _elapsed_years_from_first_nonzero(val[col], periods_per_year)
        return elapsed_df

    raise TypeError("Input must be pandas Series or DataFrame")


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
                 # Treat a 100 % loss as accum = 0 rather than share price = 0
                 # and Forward fill the previous return
                 # COULD GIVE AN INCORRECT RESULT IF THE SHARE PRICE IS ZERO, NOT THE ACCUM
                 .replace(-1, np.nan)).ffill()
         
    return basic_ret

def basic_total_return(val, cash_flows, div, date=None, use_initial_CF=False):
    '''
    basic return = (V1 - V0 - CF + DV) / (V0 + CF) 
    where, 
    V0 = starting value 
    V1 = ending value
    CF = sum of cash flows into and out of the portfolio
    assumes cash flows were at the beginning of the performance period, therefore the cash flows 
    'earned' part of the gains
    DV = dividend income
    
    https://www.kitces.com/blog/twr-dwr-irr-calculations-performance-reporting-software-methodology-gips-compliance/
    
    Parameters
    ----------
    val : pandas.DataFrame or pandas.Series
        Cumulative dollar value of each stock holdings. Data should be time series indexed.
        Each column is assummed to be a different stock in the portfolio.
    cash_flows : pandas.DataFrame or pandas.Series
        Dollar value of cash flows into or out of the portfolio. Data should be time series indexed.
        Each column is assummed to be a different stock in the portfolio
    div : pandas.DataFrame or pandas.Series
        Dollar value of Dividend income. Data should be time series indexed.
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
    div = div.loc[date:]
    
    if use_initial_CF == False:
        # V0 = value at time zero
        V0 = val.iloc[0]
    else:
        # V0 = cash flows at index zero
        V0 = cash_flows.iloc[0]
    
    basic_tot_ret = (((val - V0 - cash_flows.iloc[1:].cumsum() + div.cumsum())
                 / (V0 + cash_flows.iloc[1:].cumsum()))
                 .fillna(0)
                 # Treat a 100 % loss as accum = 0 rather than share price = 0
                 # and Forward fill the previous return
                 .replace(-1, np.nan)).ffill()
              
    return basic_tot_ret


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
    
    # Find elapsed years from first non-zero point and avoid zero-year exponents.
    num_years = _elapsed_years_from_first_nonzero(val)
    
    basic_ret_ann = np.power(basic_return(val, cash_flows, use_initial_CF=use_initial_CF) + 1, 
                             1 / num_years) - 1
    
    return basic_ret_ann    


def basic_total_return_annualised(val, cash_flows, div, date=None, use_initial_CF=False):
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
    div = div.loc[date:]
    
    # Find elapsed years from first non-zero point and avoid zero-year exponents.
    num_years = _elapsed_years_from_first_nonzero(val)
    
    basic_tot_ret_ann = np.power(basic_total_return(val, cash_flows, div, use_initial_CF=use_initial_CF) + 1, 
                             1 / num_years) - 1
    
    return basic_tot_ret_ann    


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
    
    weighted_changes = (val.shift(1) * price.pct_change()).sum(axis=1)
    previous_value = val.shift(1).sum(axis=1).replace(0, np.nan)
    gain = (weighted_changes / previous_value).replace([np.inf, -np.inf], np.nan).fillna(0)
    
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
    
    # Prepare the data
    val, cash_flows = prepare_data(val, cash_flows, date=date)
    
    MDR = pd.DataFrame([])
    for column in val:
        
        vcol = val[column]
        ccol = cash_flows[column]
        
        if (vcol == 0).all():
            MDR_individual = pd.Series(0, index=vcol.index, name=vcol.name)
       
        else:
            # Intial value of stock holding    
            initial_val = vcol.iloc[0]
            
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
                              # Treat a 100 % loss as accum = 0 rather than share price = 0
                              # and Forward fill the previous return
                              .replace(-1, np.nan)).ffill()
            
            # Set return to 0 if val of the holding = 0
            # MDR_individual[vcol==0] = 0
    
        MDR = pd.merge(MDR, MDR_individual, how='outer', left_index=True, right_index=True)
        
    return MDR


def time_weighted_total_return(val, cash_flows, div, date=None, use_initial_CF=False):
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
    
    # Prepare the data
    val, cash_flows, div = prepare_data(val, cash_flows, div, date=date)
    
    MDR = pd.DataFrame([])
    for column in val:
        
        vcol = val[column]
        ccol = cash_flows[column]
        dcol = div[column]
        
        if (vcol == 0).all():
            MDR_individual = pd.Series(0, index=vcol.index, name=vcol.name)
       
        else:
            # Intial value of stock holding    
            initial_val = vcol.iloc[0]
            
            # Start from first non-zero row
            start_index = val[vcol!=0].index[0]
            vcol = vcol.loc[start_index:]        
            ccol = ccol.loc[start_index:]   
            dcol = dcol.loc[start_index:]     
            
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
            MDR_individual = (((vcol - V0 - CF_sum + dcol.cumsum()) / (V0 + CF_time))
                              .fillna(0)
                              # Treat a 100 % loss as accum = 0 rather than share price = 0
                              # and Forward fill the previous return
                              .replace(-1, np.nan)).ffill()
            
            # Set return to 0 if val of the holding = 0
            # MDR_individual[vcol==0] = 0
    
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
    
    # Prepare the data
    val, cash_flows = prepare_data(val, cash_flows, date=date)      
    
    # Find elapsed years from first non-zero point and avoid zero-year exponents.
    num_years = _elapsed_years_from_first_nonzero(val)
       
    MDR_ann = np.power(
        time_weighted_return(val, cash_flows, use_initial_CF=use_initial_CF) + 1,
        1 / num_years,
    ) - 1
        
    return MDR_ann


def time_weighted_total_return_annualised(val, cash_flows, div, date=None, use_initial_CF=False):
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

    # Prepare the data
    val, cash_flows, div = prepare_data(val, cash_flows, div, date=date)
    
    # Find elapsed years from first non-zero point and avoid zero-year exponents.
    num_years = _elapsed_years_from_first_nonzero(val)
       
    MDR_ann = np.power(
        time_weighted_total_return(val, cash_flows, div, use_initial_CF=use_initial_CF) + 1,
        1 / num_years,
    ) - 1
        
    return MDR_ann


def dollar_weighted_return(val, cash_flows, date=None, use_initial_CF=False, resample_freq='auto'):
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
        Each column is assumed to be a different stock in the portfolio.
    cash_flows : pandas.DataFrame or pandas.Series
        Dollar value of cash flows into or out of the portfolio. Data should be time series indexed.
        Each column is assumed to be a different stock in the portfolio.
    date : string, optional
        Optional date string to pass to the Datetime index set the start date for the portfolio. 
        Full or partial string can be provided eg '20210415' or '2018'. The default is None.
    use_initial_CF : bool, optional
        Use the first row of cash_flow as the initial portfolio value instead of the first row
        of val. If the first date in the dataframe represents the first purchase date of the 
        portfolio then use_initial_CF should be set to True to give the correct cost base. 
        The default is False.
    resample_freq : str, optional
        Frequency for resampling the data. Options are 'auto', 'W' (weekly), 'M' (monthly), 'Q' (quarterly).
        If 'auto', the function will automatically choose a frequency to keep the number of rows < 150.
        The default is 'auto'.

    Returns
    -------
    DWR : pandas.DataFrame
        Dollar-weighted return (%) calculated for each stock and for each date in the resampled time series,
        representing the total return since the start date.
    '''
    # MDR on a per stock basis.
    # start from first non-zero accumulation

    # Prepare the data
    val, cash_flows = prepare_data(val, cash_flows, date=date)

    resample_freq = _resolve_dwr_resample_freq(val, resample_freq, base_rows=100)
    
    DWR = pd.DataFrame([])
    for column in val:
        vcol = val[column]
        ccol = cash_flows[column]

        if (vcol == 0).all():
            DWR_individual = pd.Series(0, index=vcol.index, name=vcol.name)
        else:
            # Start from first non-zero row
            start_index = vcol[vcol!=0].index[0]
            vcol = vcol.loc[start_index:]        
            ccol = ccol.loc[start_index:]    

            irr_series = (-ccol).astype(float)

            # Only use the val column for initial val/cost base if use_initial_CF == False
            # and the first row is non-zero (i.e. there are no holdings at the start date)
            # Otherwise the first cash flow can be used as the initial portfolio val (V0)
            # This matches the methodology used for Basic Return calc.
            # Initial value of stock holding
            initial_val = vcol.iloc[0]
            if (not use_initial_CF) or (initial_val == 0):
                irr_series.iloc[0] = -vcol.iloc[0]

            # Resample data
            irr_series = irr_series.resample(resample_freq).sum()
            vcol_ = vcol.resample(resample_freq).last()
            
            # Calculate IRR for each period
            irr_values = []
            for period_end in range(len(irr_series)):
                cash_stream = np.concatenate(
                    [irr_series.iloc[: period_end + 1].to_numpy(), [vcol_.iloc[period_end]]]
                )
                irr_values.append(npf.irr(cash_stream))

            irr_calc = pd.Series(irr_values, index=irr_series.index, name=column)

            # Convert periodic IRR to cumulative return since start
            period_count = np.arange(1, len(irr_calc) + 1)
            DWR_individual = (
                np.power(1 + irr_calc, period_count) - 1
            ).replace([np.inf, -np.inf], np.nan).fillna(0).replace(-1, np.nan).ffill()

        DWR = pd.merge(DWR, DWR_individual, how='outer', left_index=True, right_index=True)

    return DWR


def dollar_weighted_total_return(val, cash_flows, div, date=None, use_initial_CF=False, resample_freq='auto'):
    '''
    Calculates the dollar-weighted total return based on the Modified-Dietz formula, including dividends.
    time weighted return = (V1 - V0 - CF - Div) / (V0 + CF(t) + Div(t)) 
    where, 
    V0 = starting value 
    V1 = ending value
    CF = sum of cash flows into and out of the portfolio
    CF(t) are cash flows weighted for time in the portfolio
    Div = sum of dividends received
    Div(t) are dividends weighted for time in the portfolio
    
    https://www.kitces.com/blog/twr-dwr-irr-calculations-performance-reporting-software-methodology-gips-compliance/
    
    Parameters
    ----------
    val : pandas.DataFrame or pandas.Series
        Cumulative dollar value of each stock holdings. Data should be time series indexed.
        Each column is assumed to be a different stock in the portfolio.
    cash_flows : pandas.DataFrame or pandas.Series
        Dollar value of cash flows into or out of the portfolio. Data should be time series indexed.
        Each column is assumed to be a different stock in the portfolio.
    div : pandas.DataFrame or pandas.Series
        Dollar value of dividends received. Data should be time series indexed.
        Each column is assumed to be a different stock in the portfolio.
    date : string, optional
        Optional date string to pass to the Datetime index set the start date for the portfolio. 
        Full or partial string can be provided eg '20210415' or '2018'. The default is None.
    use_initial_CF : bool, optional
        Use the first row of cash_flow as the initial portfolio value instead of the first row
        of val. If the first date in the dataframe represents the first purchase date of the 
        portfolio then use_initial_CF should be set to True to give the correct cost base. 
        The default is False.
    resample_freq : str, optional
        Frequency for resampling the data. Options are 'auto', 'W' (weekly), 'M' (monthly), 'Q' (quarterly).
        If 'auto', the function will automatically choose a frequency to keep the number of rows < 150.
        The default is 'auto'.

    Returns
    -------
    DWR : pandas.DataFrame
        Dollar-weighted total return (%) calculated for each stock and for each date in the resampled time series,
        representing the total return since the start date, including dividends.
    '''
    # Prepare the data
    val, cash_flows, div = prepare_data(val, cash_flows, div, date=date)

    resample_freq = _resolve_dwr_resample_freq(val, resample_freq, base_rows=100)
    
    DWR = pd.DataFrame([])
    for column in val:
        vcol = val[column]
        ccol = cash_flows[column]
        dcol = div[column]

        if (vcol == 0).all():
            DWR_individual = pd.Series(0, index=vcol.index, name=vcol.name)
        else:
            # Initial value of stock holding
            initial_val = vcol.iloc[0]
            
            # Start from first non-zero row
            start_index = vcol[vcol!=0].index[0]
            vcol = vcol.loc[start_index:]        
            ccol = ccol.loc[start_index:]    
            dcol = dcol.loc[start_index:]    

            irr_series = (-ccol + dcol).astype(float)

            # Only use the val column for initial val/cost base if use_initial_CF == False
            # and the first row is non-zero (i.e. there are no holdings at the start date)
            # Otherwise the first cash flow can be used as the initial portfolio val (V0)
            # This matches the methodology used for Basic Return calc.
            
            if (not use_initial_CF) or (initial_val == 0):
                irr_series.iloc[0] = -vcol.iloc[0]

            # Resample data
            irr_series = irr_series.resample(resample_freq).sum()
            vcol_ = vcol.resample(resample_freq).last()
            
            # Calculate IRR for each period
            irr_values = []
            for period_end in range(len(irr_series)):
                cash_stream = np.concatenate(
                    [irr_series.iloc[: period_end + 1].to_numpy(), [vcol_.iloc[period_end]]]
                )
                irr_values.append(npf.irr(cash_stream))

            irr_calc = pd.Series(irr_values, index=irr_series.index, name=column)

            # Convert periodic IRR to cumulative return since start
            period_count = np.arange(1, len(irr_calc) + 1)
            DWR_individual = (
                np.power(1 + irr_calc, period_count) - 1
            ).replace([np.inf, -np.inf], np.nan).fillna(0).replace(-1, np.nan).ffill()

        DWR = pd.merge(DWR, DWR_individual, how='outer', left_index=True, right_index=True)

    return DWR


def dollar_weighted_return_endpoint(val, cash_flows, date=None, use_initial_CF=False, resample_freq='auto'):
    val, cash_flows = prepare_data(val, cash_flows, date=date)
    resample_freq = _resolve_dwr_resample_freq(val, resample_freq, base_rows=100)
    endpoints = {}

    for column in val:
        vcol = val[column]
        ccol = cash_flows[column]
        if (vcol == 0).all():
            endpoints[column] = 0.0
            continue

        start_index = vcol[vcol != 0].index[0]
        vcol = vcol.loc[start_index:]
        ccol = ccol.loc[start_index:]
        irr_series = (-ccol).astype(float)

        initial_val = vcol.iloc[0]
        if (not use_initial_CF) or (initial_val == 0):
            irr_series.iloc[0] = -vcol.iloc[0]

        irr_series = irr_series.resample(resample_freq).sum()
        vcol_ = vcol.resample(resample_freq).last()
        cash_stream = np.concatenate([irr_series.to_numpy(), [vcol_.iloc[-1]]])
        irr = npf.irr(cash_stream)
        if pd.isna(irr):
            endpoints[column] = 0.0
        else:
            endpoints[column] = float(np.power(1 + irr, len(irr_series)) - 1)

    return pd.Series(endpoints)


def dollar_weighted_total_return_endpoint(val, cash_flows, div, date=None, use_initial_CF=False, resample_freq='auto'):
    val, cash_flows, div = prepare_data(val, cash_flows, div, date=date)
    resample_freq = _resolve_dwr_resample_freq(val, resample_freq, base_rows=100)
    endpoints = {}

    for column in val:
        vcol = val[column]
        ccol = cash_flows[column]
        dcol = div[column]
        if (vcol == 0).all():
            endpoints[column] = 0.0
            continue

        initial_val = vcol.iloc[0]
        start_index = vcol[vcol != 0].index[0]
        vcol = vcol.loc[start_index:]
        ccol = ccol.loc[start_index:]
        dcol = dcol.loc[start_index:]

        irr_series = (-ccol + dcol).astype(float)
        if (not use_initial_CF) or (initial_val == 0):
            irr_series.iloc[0] = -vcol.iloc[0]

        irr_series = irr_series.resample(resample_freq).sum()
        vcol_ = vcol.resample(resample_freq).last()
        cash_stream = np.concatenate([irr_series.to_numpy(), [vcol_.iloc[-1]]])
        irr = npf.irr(cash_stream)
        if pd.isna(irr):
            endpoints[column] = 0.0
        else:
            endpoints[column] = float(np.power(1 + irr, len(irr_series)) - 1)

    return pd.Series(endpoints)


def contribution_analysis(
    val,
    cash_flows,
    div,
    fx_rates=None,
    date=None,
    include_total=True,
):
    """
    Compute per-ticker contribution decomposition for a selected period.

    Components:
    - Price ($)    = local-currency price effect converted to target currency
    - Dividend ($) = sum(dividend cash over period)
    - FX ($)       = residual (Total - Price - Dividend)
    - Total ($)    = end - start - net_cash_flows_ex_start + dividends

    Contribution (%) is Total($) divided by portfolio start value.
    """
    val, cash_flows, div = prepare_data(val, cash_flows, div, date=date)
    if val.empty:
        return pd.DataFrame(
            columns=[
                "Price ($)",
                "Dividend ($)",
                "FX ($)",
                "Total ($)",
                "Contribution (%)",
                "Contribution Share of Total (%)",
            ]
        )

    tickers = list(val.columns)
    rows = []

    start_vals = pd.to_numeric(val.iloc[0], errors="coerce").fillna(0.0)
    start_portfolio_value = float(start_vals.sum())
    denom = start_portfolio_value if abs(start_portfolio_value) > 1e-12 else np.nan

    for ticker in tickers:
        v = pd.to_numeric(val[ticker], errors="coerce").fillna(0.0)
        cf = pd.to_numeric(cash_flows[ticker], errors="coerce").fillna(0.0)
        dv = pd.to_numeric(div[ticker], errors="coerce").fillna(0.0)

        v_start = float(v.iloc[0])
        v_end = float(v.iloc[-1])
        net_cf_ex_start = float(cf.iloc[1:].sum()) if len(cf) > 1 else 0.0
        dividend_component = float(dv.sum())
        total_component = v_end - v_start - net_cf_ex_start + dividend_component
        price_component = v_end - v_start - net_cf_ex_start
        fx_component = 0.0
        if isinstance(fx_rates, pd.DataFrame) and ticker in fx_rates.columns:
            fx_col = pd.to_numeric(fx_rates[ticker], errors="coerce").reindex(v.index).ffill()
            first_valid = fx_col.first_valid_index()
            last_valid = fx_col.last_valid_index()
            if first_valid is not None and last_valid is not None:
                first_fx = float(fx_col.loc[first_valid])
                last_fx = float(fx_col.loc[last_valid])
                if np.isfinite(first_fx) and first_fx != 0 and np.isfinite(last_fx):
                    # Remove FX to derive local-currency series, compute local price effect,
                    # then convert back to target-currency and treat FX as residual.
                    local_v = (v / fx_col.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).ffill().fillna(0.0)
                    local_cf = (cf / fx_col.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
                    local_v_start = float(local_v.iloc[0])
                    local_v_end = float(local_v.iloc[-1])
                    local_cf_ex_start = float(local_cf.iloc[1:].sum()) if len(local_cf) > 1 else 0.0
                    local_price_component = local_v_end - local_v_start - local_cf_ex_start
                    price_component = local_price_component * last_fx
                    fx_component = total_component - price_component - dividend_component

        contribution_pct = (total_component / denom * 100.0) if pd.notna(denom) else np.nan

        rows.append(
            {
                "Ticker": ticker,
                "Price ($)": float(price_component),
                "Dividend ($)": float(dividend_component),
                "FX ($)": float(fx_component),
                "Total ($)": float(total_component),
                "Contribution (%)": float(contribution_pct) if pd.notna(contribution_pct) else np.nan,
            }
        )

    out = pd.DataFrame(rows).set_index("Ticker").sort_values("Total ($)", ascending=False)
    total_sum = float(out["Total ($)"].sum()) if not out.empty else 0.0
    if abs(total_sum) > 1e-12:
        out["Contribution Share of Total (%)"] = (out["Total ($)"] / total_sum) * 100.0
    else:
        out["Contribution Share of Total (%)"] = np.nan

    if include_total:
        total_row = pd.DataFrame(
            {
                "Price ($)": [float(out["Price ($)"].sum())],
                "Dividend ($)": [float(out["Dividend ($)"].sum())],
                "FX ($)": [float(out["FX ($)"].sum())],
                "Total ($)": [float(out["Total ($)"].sum())],
                "Contribution (%)": [
                    float(out["Total ($)"].sum() / denom * 100.0) if pd.notna(denom) else np.nan
                ],
                "Contribution Share of Total (%)": [100.0 if abs(total_sum) > 1e-12 else np.nan],
            },
            index=["TOTAL"],
        )
        out = pd.concat([out, total_row], axis=0)

    return out


def rolling_period_returns(return_series_pct, windows_years=(1, 3, 5), periods_per_year=261):
    """
    Compute rolling period returns from a cumulative return series expressed in percent.
    """
    if return_series_pct is None:
        return pd.DataFrame()
    s = pd.to_numeric(return_series_pct, errors="coerce")
    if not isinstance(s, pd.Series):
        s = pd.Series(s)
    s = s.dropna()
    if s.empty:
        return pd.DataFrame(index=getattr(return_series_pct, "index", None))

    growth = (s / 100.0) + 1.0
    out = pd.DataFrame(index=s.index)
    for years in windows_years:
        lookback = int(periods_per_year * years)
        if len(growth) <= lookback:
            continue
        col = f"{years}Y"
        out[col] = (growth / growth.shift(lookback) - 1.0) * 100.0
    return out


def rolling_return_comparison(
    portfolio_return_pct,
    benchmark_return_pct,
    windows_years=(1, 3, 5),
    periods_per_year=261,
):
    """
    Build rolling return comparison tables for portfolio and benchmark.
    """
    roll_port = rolling_period_returns(
        portfolio_return_pct, windows_years=windows_years, periods_per_year=periods_per_year
    )
    roll_bench = rolling_period_returns(
        benchmark_return_pct, windows_years=windows_years, periods_per_year=periods_per_year
    )

    common_idx = roll_port.index.intersection(roll_bench.index)
    if len(common_idx) > 0:
        roll_port = roll_port.loc[common_idx]
        roll_bench = roll_bench.loc[common_idx]

    available_windows = [c for c in roll_port.columns if c in roll_bench.columns]
    if available_windows:
        roll_port = roll_port[available_windows]
        roll_bench = roll_bench[available_windows]

    summary_rows = []
    for w in available_windows:
        p = roll_port[w].dropna()
        b = roll_bench[w].dropna()
        if p.empty or b.empty:
            continue
        p_last = float(p.iloc[-1])
        b_last = float(b.iloc[-1])
        summary_rows.append(
            {
                "Window": w,
                "Portfolio (%)": p_last,
                "Benchmark (%)": b_last,
                "Excess (%)": p_last - b_last,
            }
        )

    summary = pd.DataFrame(summary_rows)
    return roll_port, roll_bench, summary
