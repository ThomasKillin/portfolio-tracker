import share_tracking
import finnhub_tracking
import performance_calcs
import alpha_vantage_tracking

#filename = r'C:\Python\portfolio-tracker\deprecated\shares_check_QBE_COL.csv'
filename = r'C:\Python\portfolio-tracker\default portfolio\Portfolio_2023-24.csv'
filename = r'C:\Python\portfolio-tracker\deprecated\shares_check_QBE.csv'

import_a = share_tracking.get_userdata(filename)
portfolio = alpha_vantage_tracking.merge_pricedata(import_a, 'NVDA')
#portfolio = share_tracking.merge_pricedata(import_a, 'STW.AX')
#portfolio = finnhub_tracking.merge_pricedata(import_a, 'STW.AX')
processed_portfolio = share_tracking.process_data(portfolio)

# Convert the portfolio to a target currency (e.g., AUD)
target_currency = 'AUD'
converted_portfolio = share_tracking.convert_currency(processed_portfolio, target_currency)

val, cash_flows, price, accum, shares, div_tot, div = share_tracking.extract_parameters(processed_portfolio)

dwr = performance_calcs.dollar_weighted_total_return(val, cash_flows, div_tot, use_initial_CF=True)
br = performance_calcs.basic_return(val, cash_flows, use_initial_CF=True)
twr = performance_calcs.time_weighted_total_return(val, cash_flows, div_tot, use_initial_CF=True)

val_, cash_flows_, price_, accum_, shares_, div_tot_, div_ = share_tracking.extract_parameters(converted_portfolio)


dwr_c = performance_calcs.dollar_weighted_total_return(val_.sum(axis=1), 
                                                       cash_flows_.sum(axis=1),
                                                       div_tot_.sum(axis=1)) * 100

br_c = performance_calcs.basic_return(val.sum(axis=1), cash_flows.sum(axis=1))
#btr = basic_total_return(val, cash_flows, div)
#import matplotlib.pyplot as plt
df = share_tracking.stock_summary(processed_portfolio, 'STW.AX', date=None, styles=False, calc_method="basic", currency=None)
# MULTIINDEX SLICING
# idx = pd.IndexSlice
# portfolio.loc[:,idx[['Adjustments'], idx['CBA.AX']]]