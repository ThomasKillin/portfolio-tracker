import requests
from datetime import datetime
import config

def fetchStockData(symbol, start_time, end_time, region='US'):
    '''
    Uses the 'requests' library and the Yahoo finance API to extract stock price data
    between the 'start_time' and 'end_time' arguments. Return stock data in json format.
    Requires a valid API key to be saved in the config.py file as the variable 'API_key'.
    
    Parameters
    ----------
    symbol : string
        Stock ticker symbol.
    start_time : int
        Unix timestamp, eg 1235088000
    end_time : int
        Unix timestamp, eg 1235088000

    Returns
    -------
    json
        Time series data of stock prices, including opening and closing prices.

    '''
     
    url = "https://apidojo-yahoo-finance-v1.p.rapidapi.com/stock/v2/get-chart"
    
    querystring = {"period2":end_time,"period1":start_time,"region":region,"interval":"1d","symbol":symbol}
    
    headers = {
        'x-rapidapi-host': "apidojo-yahoo-finance-v1.p.rapidapi.com",
        'x-rapidapi-key': config.API_key
        }
    
    response = requests.request("GET", url, headers=headers, params=querystring)
      
    return response.json()


def parseTimestamp(inputdata):
    '''
    Takes inputdata in json format and parses the timestamp data and returns in ndarray format.

    Parameters
    ----------
    inputdata : json
        Time series data of stock prices returned from fetchStockData().

    Returns
    -------
    calendertime : ndarray
        NumPy ndarray of formatted strings. Each string is a timestamp in format %m/%d/%Y

    '''

    timestamplist = []
      
    timestamplist.extend(inputdata["chart"]["result"][0]["timestamp"])
      
    calendertime = []
      
    for ts in timestamplist:
      dt = datetime.fromtimestamp(ts)
      calendertime.append(dt.strftime("%m/%d/%Y"))
      
    return calendertime



def parseValues(inputdata):
    '''
    Takes inputdata in json format and parses the stock price data and returns in list format.

    Parameters
    ----------
    inputdata : json
        Time series data of stock prices returned from fetchStockData().

    Returns
    -------
    valueList : list
        List of stock closing prices

    '''
    valueList = []
    valueList.extend(inputdata["chart"]["result"][0]["indicators"]["quote"][0]["close"])
    
    return valueList



def attachEvents(inputdata):
    '''
    Takes inputdata in json format and generates a list of string "close" with matching length

    Parameters
    ----------
    inputdata : json
        Time series data of stock event returned from fetchStockData().

    Returns
    -------
    eventlist : list
        List of string "close" with same length as inputdata

    '''
    
    eventlist = []
      
    for i in range(0,len(inputdata["chart"]["result"][0]["timestamp"])):
      eventlist.append("close")
      
    return eventlist



