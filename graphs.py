import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import performance_calcs as calc


#### PLOT PORTFOLIO PERFORMANCE
# PLOT % GAIN
#stock_tickers_selection = stocks
def plot_portfolio_gain(val, cash_flows, index_price, date=None):

    #init_CF = (True if date == None else False)
    init_CF = (val.shape == val[date:].shape)
    #plt.plot(dh.index, (dh['IDX_benchmark'] - dh['IDX_benchmark'][0]) / 
    #         dh['IDX_benchmark'][0] * 100, label='benchmark_index')    
    
    fig1 = plt.figure(figsize=(8.5, 3.5), dpi=150)
    ax1 = fig1.add_subplot(121)
    
    #ax1.plot(dh.index, (dh['IDX'] - dh['IDX'][0]) / dh['IDX'][0] * 100, label='portfolio_index')    
    ax1.plot(calc.basic_return(val.sum(axis=1), cash_flows.sum(axis=1), date=date, use_initial_CF=init_CF) * 100, 
             label='Basic Return')   
    ax1.plot(calc.time_weighted_return(val.sum(axis=1), cash_flows.sum(axis=1), date=date, use_initial_CF=init_CF) * 100, 
             label='Time Weighted Return')
    ax1.plot(calc.basic_return(index_price, pd.Series(0, index=index_price.index), date=date) * 100, 
             label='benchmark index')
    
    ax1.set_ylabel('Gain (%)')
    ax1.grid(True)
    ax1.set_title('Portfolio Gain')
    ax1.legend(fontsize='small')
    
    #ax1.figure.autofmt_xdate()
    
    #print('Benchmark gain = {:.2f} %'.format((dh[index][-1] - dh[index][0]) / dh[index][0] * 100))
    #print('Basic return = {:.2f} %'.format(dh['BR'][-1]*100))
    #print('Modified Dietz return = {:.2f} %'.format(dh['MDR'][-1]*100))

    ### PORTFOLIO DOLLAR GAIN VS TIME
    ax2 = fig1.add_subplot(122)
    ax2.plot(val.sum(axis=1) / 1000)
    ax2.set_ylabel('Value (*$1000s)')
    ax2.grid(True)
    ax2.set_title('Total Portfolio Value')
    #ax4.figure.autofmt_xdate()
    
    #plt.tight_layout()
    # Rotate x tick labels to avoid overlapping labels
    plt.setp(ax1.get_xticklabels(), rotation=30, horizontalalignment='right')
    plt.setp(ax2.get_xticklabels(), rotation=30, horizontalalignment='right')
    #plt.setp(ax4.get_xticklabels(), rotation=30, horizontalalignment='right')
    
    # Adjust space between subplots
    fig1.subplots_adjust(wspace=.25)
    plt.show()    
    
    return fig1


    
def plot_stock_gain(val, cash_flows, date=None, use_initial_CF=False):
    
    ### PLOT GAIN FOR INDIVIDUAL STOCKS
    fig1 = plt.figure(figsize=(4.25, 3.5), dpi=150)
    ax1 = fig1.add_subplot(111)
    
    if isinstance(val, pd.DataFrame):
        plot_label = val.columns
        legend_cols = round(len(val.columns)/15) + 1
    if isinstance(val, pd.Series):
        plot_label = val.name
        legend_cols = 1
        
    ax1.plot(calc.time_weighted_return(val, cash_flows, date=date, use_initial_CF=use_initial_CF) 
             * 100, label = plot_label)
             
    ax1.legend(fontsize='small', loc='best', ncol=legend_cols)
    #ax2.figure.autofmt_xdate()
    ax1.set_title('Stock Gain')
    #ax2.legend()
    ax1.legend(loc='center left', fontsize='x-small', ncol=legend_cols, bbox_to_anchor=(1, 0.5))
    #ax.set_ylim(-100, 200)
    ax1.set_ylabel('Gain (%)')
    ax1.grid(True)
    
    # Rotate x tick labels to avoid overlapping labels
    plt.setp(ax1.get_xticklabels(), rotation=30, horizontalalignment='right')
    #plt.setp(ax2.get_xticklabels(), rotation=30, horizontalalignment='right')
    
    # Adjust space between subplots
    #fig1.subplots_adjust(hspace=0.65)
    #fig1.subplots_adjust(wspace=.25)
    plt.show()
    
    return fig1
    
def plot_stock_holdings(val, date=None):
    
    ### PLOT HOLDINGS OF EACH STOCK
    fig1 = plt.figure(figsize=(4.25, 3.5), dpi=150)
    ax1 = fig1.add_subplot(111)
    
    #ax1.barh(labels, holdings)
    nonzero_cols = val.iloc[-1][val.iloc[-1]!=0]
    pct_holdings = nonzero_cols / nonzero_cols.sum() * 100
    ax1.barh(list(nonzero_cols.index), list(pct_holdings))
    ax1.set_xlabel('Percent of Portfolio (%)')
    ax1.set_title('Current Stock Holdings')
    ax1.grid(True)
    plt.show()
    #ax3.figure.autofmt_xdate()
    
    return fig1

def plot_annualised_return(val, cash_flows, index_price, date=None, use_initial_CF=False):
    
    fig1 = plt.figure(figsize=(4.25, 3.5), dpi=150)
    br = (calc.basic_return_annualised(val, cash_flows, date=date, 
                                       use_initial_CF=use_initial_CF).iloc[-1] * 100)
    br = br[br!=0]
    twr = (calc.time_weighted_return_annualised(val, cash_flows, date=date, 
                                                use_initial_CF=use_initial_CF).iloc[-1] * 100)
    twr = twr[twr!=0]
    benchmark = (calc.time_weighted_return_annualised(index_price, 
                                                      pd.Series(0, index=index_price.index, 
                                                                name=index_price.name), 
                                                      date=date)
                                                     .iloc[-1] * 100)
    #label='Basic Return'
    width = 1 / len(br) / 2.3
    x = np.linspace(0, 1, len(br))
    plt.bar(x, list(br), width=-width, tick_label = br.index, align = 'edge', label='Ann. basic return')
    plt.bar(x, list(twr), width=width, tick_label = twr.index, align = 'edge', label='Ann. time-weighted return')
    plt.hlines(benchmark, 0, 1, colors='r', linestyles='dashed', label='Benchmark')
    plt.legend(fontsize='x-small')
    plt.title('Annualised returns')
    plt.xticks(rotation=90)
    plt.ylabel('Gain (%)')
    plt.grid(axis='x')
    plt.show()
    
    return fig1
