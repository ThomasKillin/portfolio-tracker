import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import performance_calcs as calc
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import plotly.express as px


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

"""
def plot_portfolio_gain_plotly(val, cash_flows, index_price, div=None, date=None, calc_method='basic'):
    
    init_CF = (val.shape == val[date:].shape)
    
    colors = px.colors.sequential.Aggrnyl
    
    if calc_method == 'basic':
        y1 = calc.basic_return(val.sum(axis=1), cash_flows.sum(axis=1), date=date, use_initial_CF=init_CF) * 100
        y2 = (calc.time_weighted_return(val.sum(axis=1), cash_flows.sum(axis=1), date=date, use_initial_CF=init_CF) * 100)[0]
        y3 = calc.basic_return(index_price, pd.Series(0, index=index_price.index), date=date) * 100
    elif calc_method == 'total':
        y1 = calc.basic_total_return(val.sum(axis=1), cash_flows.sum(axis=1), div.sum(axis=1), date=date, use_initial_CF=init_CF) * 100
        y2 = (calc.time_weighted_total_return(val.sum(axis=1), cash_flows.sum(axis=1), div.sum(axis=1), date=date, use_initial_CF=init_CF) * 100)[0]
        y3 = calc.basic_total_return(index_price, pd.Series(0, index=index_price.index), div, date=date) * 100
    
    # Create subplot for portfolio gain vs. time
    fig = make_subplots(rows=1, cols=2, 
                        column_widths=[1, 1],
                        subplot_titles=("<b>Portfolio Gain", "<b>Total Portfolio Value"))
    
    # Plot portfolio gain
    fig.add_trace(go.Scatter(x=val[date:].index,
                             y=y1,
                             name="Basic Return",
                             legendgroup='group1',
                             mode='lines', line=dict(color=colors[0])), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=val[date:].index,
                             y=y2,
                             name="Time Weighted Return",
                             legendgroup='group1',
                             line=dict(color=colors[3])), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=index_price[date:].index,
                             y=y3,
                             name="Benchmark Index",
                             legendgroup='group1',
                             line=dict(color=colors[5])), row=1, col=1)

    # Set layout for portfolio gain subplot
    fig.update_yaxes(title_text="Gain (%)", row=1, col=1)
    fig.update_xaxes(title_text="Date", row=1, col=1)
    #fig.update_layout(title="<b>Portfolio Gain</b>", showlegend=True)
    
    
    # Plot total portfolio value
    fig.add_trace(go.Scatter(x=val.index,
                             y=val.sum(axis=1) / 1000,  
                             name="Total Portfolio Value",
                             legendgroup='group2',
                             showlegend=False,
                             line=dict(color='rgb(71, 157, 201)')), 
                             row=1, col=2)
                             #line=dict(color=colors[0])), row=1, col=2)

    # Set layout for total portfolio value subplot
    fig.update_yaxes(title_text="Value (*$1000s)", row=1, col=2)
    fig.update_xaxes(title_text="Date", row=1, col=2)
    #fig.update_layout(title="<b>Total Portfolio Value</b>", showlegend=True)
    
    fig.update_layout(showlegend=True,
                      autosize=False,
                      width=1400,
                      height=550,
                      xaxis=dict(showgrid=True),
                      yaxis=dict(showgrid=True))
    
    fig['layout']['xaxis2'].update(showgrid=True)
    fig.update_annotations(font_size=20)
    # Show the plot
    #fig.show()
    
    return fig
"""

def plot_portfolio_gain_plotly(val, cash_flows, index_price, div=None, index_div=None, date=None, calc_method='basic'):
    
    init_CF = (val.shape == val[date:].shape)
    
    colors = px.colors.sequential.Aggrnyl
    
    def calculate_returns(calc_method):
        if calc_method == 'basic':
            y1 = calc.basic_return(val.sum(axis=1), cash_flows.sum(axis=1), date=date, use_initial_CF=init_CF) * 100
            y2 = (calc.time_weighted_return(val.sum(axis=1), cash_flows.sum(axis=1), date=date, use_initial_CF=init_CF) * 100)[0]
            y3 = calc.basic_return(index_price, pd.Series(0, index=index_price.index), date=date) * 100
        elif calc_method == 'total':
            y1 = calc.basic_total_return(val.sum(axis=1), cash_flows.sum(axis=1), div.sum(axis=1), date=date, use_initial_CF=init_CF) * 100
            y2 = (calc.time_weighted_total_return(val.sum(axis=1), cash_flows.sum(axis=1), div.sum(axis=1), date=date, use_initial_CF=init_CF) * 100)[0]
            y3 = calc.basic_total_return(index_price, pd.Series(0, index=index_price.index), index_div, date=date) * 100
        return y1.values.tolist(), y2.values.tolist(), y3.values.tolist()
    
    y1, y2, y3 = calculate_returns(calc_method)
    
    # Create subplot for portfolio gain vs. time
    fig = make_subplots(rows=1, cols=2, 
                        column_widths=[1, 1],
                        subplot_titles=("<b>Portfolio Gain", "<b>Total Portfolio Value"))
    
    # Plot portfolio gain
    fig.add_trace(go.Scatter(x=val[date:].index,
                             y=y1,
                             name="Basic Return",
                             legendgroup='group1',
                             mode='lines', line=dict(color=colors[0])), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=val[date:].index,
                             y=y2,
                             name="Time Weighted Return",
                             legendgroup='group1',
                             line=dict(color=colors[3])), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=index_price[date:].index,
                             y=y3,
                             name="Benchmark Index",
                             legendgroup='group1',
                             line=dict(color=colors[5])), row=1, col=1)

    # Set layout for portfolio gain subplot
    fig.update_yaxes(title_text="Gain (%)", row=1, col=1)
    fig.update_xaxes(title_text="Date", row=1, col=1)

    # Plot total portfolio value
    fig.add_trace(go.Scatter(x=val.index,
                             y=val.sum(axis=1) / 1000,  
                             name="Total Portfolio Value",
                             legendgroup='group2',
                             showlegend=False,
                             line=dict(color='rgb(71, 157, 201)')), 
                             row=1, col=2)

    # Set layout for total portfolio value subplot
    fig.update_yaxes(title_text="Value (*$1000s)", row=1, col=2)
    fig.update_xaxes(title_text="Date", row=1, col=2)
    
    fig.update_layout(showlegend=True,
                      autosize=False,
                      width=1400,
                      height=550,
                      xaxis=dict(showgrid=True),
                      yaxis=dict(showgrid=True))
    
    fig['layout']['xaxis2'].update(showgrid=True)
    fig.update_annotations(font_size=20)
    
    # Add buttons to toggle calculation method
    fig.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                buttons=list([
                    dict(
                        args=[{"y": [calculate_returns('basic')[0], calculate_returns('basic')[1], 
                                     calculate_returns('basic')[2], val.sum(axis=1) / 1000]}],
                        label="Basic",
                        method="update"
                    ),
                    dict(
                        args=[{"y": [calculate_returns('total')[0], calculate_returns('total')[1], 
                                     calculate_returns('total')[2], val.sum(axis=1) / 1000]}],
                        label="Total",
                        method="update"
                    )
                ]),
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.1,
                xanchor="left",
                y=1.1,
                yanchor="top"
            ),
        ]
    )
    
    return fig

def plot_portfolio_gain_plotly_(val, cash_flows, index_price, date=None):
    
    colors = px.colors.sequential.Aggrnyl
    
    init_CF = (val.shape == val[date:].shape)
    
    # Calculate basic and time-weighted returns
    basic_return = calc.basic_return(val.sum(axis=1), 
                                     cash_flows.sum(axis=1),
                                     date=date, 
                                     use_initial_CF=init_CF) * 100
    
    time_weighted_return = (calc.time_weighted_return(val.sum(axis=1), 
                                                      cash_flows.sum(axis=1), 
                                                      date=date, 
                                                      use_initial_CF=init_CF) * 100)[0]
    
    index_return = calc.basic_return(index_price, 
                                     pd.Series(0, index=index_price.index), 
                                     date=date) * 100

    # Create a subplot with 2 columns and 1 row
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Portfolio Gain", "Total Portfolio Value"),
                        column_widths=[0.6, 0.4])

    # Add trace for basic and time-weighted return
    fig.add_trace(go.Scatter(x=val.index, 
                             y=basic_return, 
                             name="Basic Return", 
                             mode='lines', 
                             line=dict(color=colors[0])), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=val.index, 
                             y=time_weighted_return, 
                             name="Time Weighted Return", 
                             mode='lines', 
                             line=dict(color=colors[3])), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=val.index, 
                             y=index_return,
                             name="Benchmark Index", 
                             mode='lines', 
                             line=dict(color=colors[5])), row=1, col=1)

    # Add trace for portfolio value
    fig.add_trace(go.Scatter(x=val.index, 
                             y=val.sum(axis=1) / 1000, 
                             name="Portfolio Value",
                             mode='lines', 
                             #line=dict(color=colors[0])), row=1, col=2)
                             line=dict(color='rgb(71, 157, 201)')), row=1, col=2)    
    # Set x-axis title for all subplots
    fig.update_xaxes(title_text="Date", row=1, col=1)
    fig.update_xaxes(title_text="Date", row=1, col=2)

    # Set y-axis title for each subplot
    fig.update_yaxes(title_text="Gain (%)", row=1, col=1)
    fig.update_yaxes(title_text="Value (*$1000s)", row=1, col=2)

    # Set subplot title font style and size
    fig.update_layout(
        title={
            "text": "<b>Portfolio Performance</b>",
            "x": 0.5,
            "y": 0.95,
            "font": dict(
                family="Arial",
                size=20,
                color="#000000"
            )
        },
        font=dict(
            family="Arial",
            size=12,
            color="#000000"
        )
    )

    # Set subplot line colors and marker styles
    #fig.update_traces(line=dict(color='#0099FF', width=2), marker=dict(size=4))

    return fig


    
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




def plot_stock_gain_plotly(val, cash_flows, date=None, use_initial_CF=False):
    """
    Plot gain for individual stocks.
    """
    
    if isinstance(val, pd.DataFrame):
        plot_labels = val.columns.to_list()
        legend_cols = round(len(val.columns)/15) + 1
    elif isinstance(val, pd.Series):
        plot_labels = [val.name]
        legend_cols = 1
        
    fig1 = go.Figure()
    
    #colors = px.colors.sequential.Aggrnyl
    
    for label in plot_labels:
        time_weighted_return = (calc.time_weighted_return(val[label], cash_flows, date=date, 
                                                          use_initial_CF=use_initial_CF) * 100)[label]
        fig1.add_trace(go.Scatter(
            #x=val.index.strftime("%Y-%m-%d %H:%M:%S").tolist(),
            x = time_weighted_return.index,
            y = time_weighted_return.to_list(),
            #color_discrete_sequence= px.colors.sequential.Plasma_r,
            #x=val.index,
            #y=(calc.time_weighted_return(val[label], cash_flows, date=date, use_initial_CF=use_initial_CF) * 100)[label].to_list(),
            name=label
        ))
    
    #fig1.update_layout(
    #    title='<b>Stock Gain',
    #    title_x=0.5,
    #    yaxis_title='Gain (%)',
    #    legend=dict(font=dict(size=10)),
    #    xaxis_tickangle=-30,
        #grid=dict(
        #    row=1,
        #    column=1,
        #    pattern=None
            #row_heights=[0.7],
            #column_widths=[0.9]
        #)
    #)
    
    # Set plot properties
    fig1.update_layout(
        width=1400,
        height=550,
        title={
            'text': 'Stock Gain',
            'x': 0.5,
            'y': 0.9,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(color='slategrey',
                    size=20)
            #    color='black'
            #)
        },
        xaxis=dict(
            title='Date',
            showgrid=True,
            gridwidth=1
            #gridcolor='White'
        ),
        yaxis=dict(
            title='Gain (%)',
            showgrid=True,
            visible=True
        ),
        #plot_bgcolor='lightgray'
    )
    
    #fig1.update_xaxes(title_text="Date")
    
    #fig1.show()
    
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


def plot_stock_holdings_plotly(val, date=None):
    
    #colors = px.colors.sequential.Aggrnyl
    
    # Get non-zero columns for last date and calculate percentage holdings
    nonzero_cols = val.iloc[-1][val.iloc[-1]!=0]
    pct_holdings = nonzero_cols / nonzero_cols.sum() * 100
    
    # Create horizontal bar chart using plotly
    fig1 = go.Figure(go.Bar(
        x=pct_holdings.values,
        y=pct_holdings.index,
        orientation='h',
        marker=dict(
            color='rgb(134, 219, 163)'
            #color='darkgreen',
            #line=dict(
            #    #color='rgba(50, 171, 96, 1.0)',
            #    #color='darkgreen',
            #    color=colors[0],
            #    width=1
            #)
        )
    ))
    
    # Set plot properties
    fig1.update_layout(
        width=700,
        height=550,
        title={
            'text': 'Current Stock Holdings',
            'x': 0.5,
            'y': 0.9,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(
                size=20,
                color='slategrey'
            )
        },
        xaxis=dict(
            title='Percent of Portfolio (%)',
            showgrid=True,
            gridwidth=1
            #gridcolor='White'
        ),
        yaxis=dict(
            showgrid=False,
            visible=True
        )
        #plot_bgcolor='lightgrey'
    )
    
    #fig1.show()
    
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



def plot_annualised_return_plotly(val, cash_flows, index_price, date=None, use_initial_CF=False):

    br = (calc.basic_return_annualised(val, cash_flows, date=date, use_initial_CF=use_initial_CF).iloc[-1] * 100)
    br = br[br!=0]
    twr = (calc.time_weighted_return_annualised(val, cash_flows, date=date, use_initial_CF=use_initial_CF).iloc[-1] * 100)
    twr = twr[twr!=0]
    benchmark = (calc.time_weighted_return_annualised(index_price, pd.Series(0, index=index_price.index, name=index_price.name), date=date).iloc[-1] * 100)
    
    colors = px.colors.sequential.Aggrnyl
    fig = make_subplots(rows=1, cols=1, subplot_titles=("Annualised returns",),
                        vertical_spacing=0.15, horizontal_spacing=0.05)

    list_ = []
    for i in range(len(br)):
        list_.append(i)
    fig = go.Figure(data=[
        go.Bar(x=[br.index[i]], y=[br[list_]], width=[0.2],
                         marker=dict(color=colors[i%len(colors)]), 
                         name='Ann. basic return', showlegend=False),
        go.Bar(x=[twr.index[i]], y=[twr[list_]], width=[0.2],
                         marker=dict(color=colors[i%len(colors)]), 
                         name='Ann. time-weighted return', showlegend=False)
        ])

    fig.add_trace(go.Scatter(x=[-0.5, 0.5], y=[benchmark, benchmark], mode='lines', 
                             line=dict(color='red', width=2, dash='dash'), name='Benchmark'))

    fig.update_yaxes(title_text='Gain (%)')
    fig.update_xaxes(tickangle=90)
    fig.update_layout(title=dict(text='Annualised returns', x=0.5, y=0.9, 
                                 font=dict(color='slategrey')), 
                      margin=dict(l=50, r=50, t=80, b=50),
                      showlegend=True, legend=dict(font=dict(size=8)), 
                      plot_bgcolor='white', hovermode='x')

    #fig.show()

    return fig

def plot_annualised_return_plotly_(val, cash_flows, index_price, date=None, use_initial_CF=False):
    
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
    
    width = 1 / len(br) / 2.3
    x = np.linspace(0, 1, len(br))
    offset = width / 2.3
    x_br = x - offset
    x_twr = x + offset
    
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x_br, y=br.values, width=width, 
                         name='Ann. basic return', marker_color='rgb(71, 157, 201)'))
    fig.add_trace(go.Bar(x=x_twr, y=twr.values, width=width, 
                         name='Ann. time-weighted return', marker_color='rgb(134, 219, 163)'))
    
    # Add benchmark line
    fig.add_trace(go.Scatter(x=[x_br[0], x_twr[-1]], y=[benchmark.values[0], benchmark.values[0]],
                             mode='lines', name='Benchmark', line=dict(color='red', dash='dash')))
    
    #fig.update_layout(title='Annualised returns', yaxis_title='Gain (%)', 
    #                  xaxis_tickangle=-90, xaxis_tickvals=x, xaxis_ticktext=br.index.tolist(),
    #                  legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
    
    #fig.update_layout(title=dict(text='Annualised returns', x=0.5, y=0.9, 
    #                             font=dict(size=18, color='black')), 
    #                  margin=dict(l=50, r=50, t=80, b=50),
    #                  showlegend=True, legend=dict(font=dict(size=8)), 
    #                  plot_bgcolor='white', hovermode='x')
    
    fig.update_layout(width=700, 
                      height=550,
                      title=dict(text='Annualised returns', x=0.5, y=0.9, 
                                 font=dict(size=20, color='slategrey')), 
                      yaxis_title='Gain (%)', 
                      xaxis_tickangle=-90, xaxis_tickvals=x, xaxis_ticktext=br.index.tolist(), 
                      showlegend=True)
                      #legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
    
    
    #fig.show()
    
    return fig





