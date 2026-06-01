# 克隆自聚宽文章：https://www.joinquant.com/post/45358
# 标题：基本面01加RSI择时
# 作者：明曦

import pandas as pd
from jqdata import *
import numpy as np
import talib 





def initialize(context):
    # setting
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.003))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5),type='stock')
    run_monthly(monthly_adjustment, 1, 'open')
    run_daily(daily_adjustment, time='9:30', reference_security='000300.XSHG')
    run_daily(prepare_stock_list, time='9:05', reference_security='000300.XSHG')
    g.stock_num =10
    g.hold_list = []
    g.primary_num=50
    
    
def prepare_stock_list(context):
    #获取已持有列表
    g.hold_list= []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)

def monthly_adjustment(context):
    yesterday = context.previous_date
    initial_list = get_all_securities().index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_paused_stock(initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    df = get_fundamentals(query(
            valuation.code,
        ).filter(
            valuation.code.in_(initial_list),
            valuation.pb_ratio.between(0,10),#市净率
            valuation.pcf_ratio<5,#市现率
            indicator.roe>0.3,#净资产收益率
            indicator.gross_profit_margin>0.3,#销售毛利率
            indicator.inc_net_profit_year_on_year>1.5#净利润同比增长率
         
        ).order_by(
        valuation.market_cap.asc()).limit(g.primary_num)).set_index('code').index.tolist()
    df1=[]
    for s in df:
        period=14
        count=period+1
        price=get_price(s,end_date=yesterday,count=count,fields=['close'])
        price=price['close'].values
        rsi=talib.RSI(price,timeperiod=period)
        if rsi[-1]<50:
            df1.append(s)
    
    df1=df1[0:g.stock_num]
    
       
    
    final_list=df1
    for stock in g.hold_list:
        if stock not in final_list:
            position = context.portfolio.positions[stock]
            close_position(position)
    
    position_count = len(context.portfolio.positions)
    final_num = len(final_list)
    if final_num > position_count:
        value = context.portfolio.cash / (final_num - position_count)
        for stock in final_list:
            if context.portfolio.positions[stock].total_amount == 0:
                if open_position(stock, value):
                    if len(context.portfolio.positions) == final_num:
                        break
 
 
def daily_adjustment(context):
    yesterday = context.previous_date
    for stock in g.hold_list:
        period=14
        count=period+1
        price=get_price(stock,end_date=yesterday,count=count,fields=['close'])
        price=price['close'].values
        rsi=talib.RSI(price,timeperiod=period)
        if rsi[-1]>70:
            position = context.portfolio.positions[stock]
            close_position(position)
        








def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=375)]


def filter_st_stock(stock_list):
	current_data = get_current_data()
	return [stock for stock in stock_list
			if not current_data[stock].is_st
			and 'ST' not in current_data[stock].name
			and '*' not in current_data[stock].name
			and '退' not in current_data[stock].name]
			
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list
    
def open_position(security, value):
	order = order_target_value_(security, value)
	if order != None and order.filled > 0:
		return True
	return False
	
def order_target_value_(security, value):
	if value == 0:
		log.debug("Selling out %s" % (security))
	else:
		log.debug("Order %s to value %f" % (security, value))
	return order_target_value(security, value)
	
def close_position(position):
	security = position.security
	order = order_target_value_(security, 0)  # 可能会因停牌失败
	if order != None:
		if order.status == OrderStatus.held and order.filled == order.amount:
			return True
	return False
	
def filter_paused_stock(stock_list):
	current_data = get_current_data()
	return [stock for stock in stock_list if not current_data[stock].paused]
