# 克隆自聚宽文章：https://www.joinquant.com/post/45510
# 标题：5年15倍的收益，年化79.93%，可实盘，拿走不谢！
# 作者：langcheng999

import pandas as pd 
from jqdata import *
from jqfactor import get_factor_values
import redis
import json


def initialize(context):
    # setting
    # 设置日志级别为error
    log.set_level('order', 'error')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 设置是否开启避免未来数据模式
    set_option('avoid_future_data', True)
    # 设置基准
    set_benchmark('000300.XSHG')
    # 设置滑点
    set_slippage(FixedSlippage(0.02))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5),type='fund')
    # strategy
    #初始化全局变量
    g.no_trading_today_signal = False
    g.stock_num = 10  # 持股数量
    g.choice = []  # 股票池
    g.just_sold = []  # just_sold标记本月涨停过的
    
    g.limit_days = 30  # 限制天数N天
    g.hold_list = []  # 已持有股票列表
    g.history_hold_list = []  # 存放N天持有过的股票，二维数组
    g.not_buy_again_list = []  # N天买过的股票,不再买入的黑名单，一维数组
    
    
    # 准备昨日涨停且正在持有的股票列表
    run_daily(prepare_high_limit_list, time='9:05', reference_security='000300.XSHG') 
    # 每天调整昨日涨停股票
    run_daily(check_limit_up, time='14:00') 
    # 每月选股
    run_monthly(my_Trader, -1 ,time='9:30', force=True) 
    # 每月调仓一次
    run_monthly(go_Trader, -1 ,time='14:55', force=True) 
    # 是否是4月份，是则清仓
    run_daily(close_account, '14:30')
    # 收盘后运行
    # run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

# 每月选股
def my_Trader(context):

    #1 all stocks
    dt_last = context.previous_date
    stocks = get_all_securities('stock', dt_last).index.tolist()
    stocks = filter_kcbj_stock(stocks)
    #2 股息率筛选排序
    # stocks = get_dividend_ratio_filter_list(context, stocks, False, 0, 0.25)  
    # stocks = get_factor_filter_list(context, stocks, 'ROAEBITTTM', False, 0, 0.2)

    #4 各种过滤
    choice = filter_st_stock(stocks)
    choice = filter_paused_stock(choice)
    choice = filter_new_stock(context, choice)
    choice = filter_limitup_stock(context,choice)
    choice = filter_limitdown_stock(context,choice)
    #5 低价股
    choice = filter_highprice_stock(context,choice)
    
    #3 基本面筛选，并根据小市值排序
    choice = get_peg(context,choice)
    
    #过滤最近买过且涨停过的股票
    recent_limit_up_list = get_recent_limit_up_stock(context, choice, g.limit_days)
    # black_list = list((set(g.not_buy_again_list).intersection(set(recent_limit_up_list))).union(set(g.just_sold)))
    black_list = list(set(g.not_buy_again_list).intersection(set(recent_limit_up_list)))
    target_list = [stock for stock in choice if stock not in black_list]
    log.info('过滤完黑名单的数量', len(target_list))
    #截取不超过最大持仓数的股票量
    choice = target_list[:min(g.stock_num, len(target_list))]
    
    g.choice = choice[:g.stock_num]


#1-1 选股模块
def get_factor_filter_list(context,stock_list,jqfactor,sort,p1,p2):
    yesterday = context.previous_date
    score_list = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].tolist()
    df = pd.DataFrame(columns=['code','score'])
    df['code'] = stock_list
    df['score'] = score_list
    df = df.dropna()
    df.sort_values(by='score', ascending=sort, inplace=True)
    filter_list = list(df.code)[int(p1*len(df)):int(p2*len(df))]
    return filter_list




# 每月调仓一次
def go_Trader(context):
    if g.no_trading_today_signal == False:

        # g.just_sold = [] #每月清零一次 g.just_sold 防止其中内容一直膨胀
        
        cdata = get_current_data()
        choice = g.choice
        # Sell，仍在选出的股票池中，则不卖
        for s in context.portfolio.positions:
            if (s not in choice and (not cdata[s].paused)) :
                log.info('Sell', s, cdata[s].name)
                order_target(s, 0)
                g.just_sold.append(s)
                
                if len(g.just_sold) >= g.limit_days:
                    g.just_sold = g.just_sold[-g.stock_num:]
        

        # buy，根据资金买入相应的金额
        position_count = len(context.portfolio.positions)
        if g.stock_num > position_count:
            psize = context.portfolio.available_cash/(g.stock_num - position_count)
            for s in choice:
                if s not in context.portfolio.positions:
                    log.info('buy', s, cdata[s].name)
                    order = order_value(s, psize) 
                    if len(context.portfolio.positions) == g.stock_num:
                        break

# 没用到此函数
def cap(context):
    current_data = get_current_data()   #获取日期
    hold_stocks = context.portfolio.positions.keys()
    for s in hold_stocks:
        q = query(valuation).filter(valuation.code == s)
        df = get_fundamentals(q)
        # log.info(s,current_data[s].name,'流值',df['circulating_market_cap'][0],'亿')
        log.info(s,current_data[s].name,'市值',df['market_cap'][0],'亿')
        log.info(s,current_data[s].name,'股价',current_data[s].last_price,'元')
        
#2-3 获取最近N个交易日内有涨停的股票
def get_recent_limit_up_stock(context, stock_list, recent_days):
    stat_date = context.previous_date
    new_list = []
    for stock in stock_list:
        df = get_price(stock, end_date=stat_date, frequency='daily', fields=['close','high_limit'], count=recent_days, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        if len(df) > 0:
            new_list.append(stock)
    return new_list
        

# 基本面筛选，并根据小市值排序
def get_peg(context,stocks):
    # 获取基本面数据
    q = query(valuation.code,
                valuation.pe_ratio,
                indicator.inc_net_profit_year_on_year,
                valuation.pe_ratio / indicator.inc_net_profit_year_on_year,# PEG
                indicator.roe / valuation.pb_ratio, # 收益率指标：ROE/PB特别适合于周期类、成长性一般企业的估值分析
                indicator.roe,
                indicator.roa,
                valuation.pb_ratio
                ).filter(
                    # valuation.pe_ratio > 0,
                    # indicator.inc_net_profit_year_on_year > 0,
                    # valuation.pe_ratio / indicator.inc_net_profit_year_on_year<1,
                    # valuation.pb_ratio < 3,
                    # indicator.roe / valuation.pb_ratio > 3.2,   #国债收益率
                    indicator.roe > 0.15,
                    indicator.roa > 0.10,
                    valuation.code.in_(stocks))
    df_fundamentals = get_fundamentals(q, date = None)       
    stocks = list(df_fundamentals.code)
    # fuandamental data
    df = get_fundamentals(query(valuation.code).filter(valuation.code.in_(stocks)).order_by(valuation.market_cap.asc()))
    choice = list(df.code)
    return choice

#1-1 根据最近一年分红除以当前总市值计算股息率并筛选排序    
def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2):
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365)
    #获取分红数据，由于finance.run_query最多返回4000行，以防未来数据超限，最好把stock_list拆分后查询再组合
    interval = 1000 #某只股票可能一年内多次分红，导致其所占行数大于1，所以interval不要取满4000
    list_len = len(stock_list)
    #截取不超过interval的列表并查询
    q = query(
        finance.STK_XR_XD.code, 
        finance.STK_XR_XD.a_registration_date, 
        finance.STK_XR_XD.bonus_amount_rmb
    ).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
    df = finance.run_query(q)
    #对interval的部分分别查询并拼接
    if list_len > interval:
        df_num = list_len // interval
        for i in range(df_num):
            q = query(
                finance.STK_XR_XD.code,
                finance.STK_XR_XD.a_registration_date,
                finance.STK_XR_XD.bonus_amount_rmb
            ).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(stock_list[interval*(i+1):min(list_len,interval*(i+2))]))
            temp_df = finance.run_query(q)
            df = df.append(temp_df)
    dividend = df.fillna(0)
    dividend = dividend.set_index('code')
    dividend = dividend.groupby('code').sum()
    temp_list = list(dividend.index) #query查询不到无分红信息的股票，所以temp_list长度会小于stock_list
    #获取市值相关数据
    q = query(valuation.code,valuation.market_cap).filter(valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1)
    cap = cap.set_index('code')
    #计算股息率
    DR = pd.concat([dividend, cap] ,axis=1, sort=False)
    DR['dividend_ratio'] = (DR['bonus_amount_rmb']/10000) / DR['market_cap']
    #排序并筛选
    DR = DR.sort_values(by=['dividend_ratio'], ascending=sort)
    final_list = list(DR.index)[int(p1*len(DR)):int(p2*len(DR))]
    return final_list
    
# 准备昨日涨停且正在持有的股票列表
def prepare_high_limit_list(context):

    # 昨日涨停列表
    g.high_limit_list = []
    #获取已持有列表
    hold_list = list(context.portfolio.positions)
    if hold_list:
        df = get_price(hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'],
                       count=1, panel=False)
        g.high_limit_list = df[df['close'] == df['high_limit']]['code'].tolist()
    #判断今天是否为账户资金再平衡的日期，空仓期一个月
    g.no_trading_today_signal =  False
    # g.no_trading_today_signal = today_is_between(context, '04-01', '04-30')
    
    #获取已持有列表
    g.hold_list= []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    #获取最近一段时间持有过的股票列表
    g.history_hold_list.append(g.hold_list)
    if len(g.history_hold_list) >= g.limit_days:
        g.history_hold_list = g.history_hold_list[-g.limit_days:]
    temp_set = set()
    for hold_list in g.history_hold_list:
        for stock in hold_list:
            temp_set.add(stock)
    g.not_buy_again_list = list(temp_set)
    

#  调整昨日涨停股票
def check_limit_up(context):
    if g.no_trading_today_signal == False:
        
        
        # 获取持仓的昨日涨停列表
        current_data = get_current_data()
        if g.high_limit_list:
            for stock in g.high_limit_list:
                # 涨停的票，涨不动了就卖掉
                if current_data[stock].last_price < current_data[stock].high_limit:
                    order_target(stock, 0)
                    log.info("[%s]涨停打开，卖出" % stock)
                    # just_sold标记本月涨停过的
                    g.just_sold.append(stock)
                    if len(g.just_sold) >= g.limit_days:
                        g.just_sold = g.just_sold[-g.stock_num:]
                else:
                    log.info("[%s]涨停，继续持有" % stock)
        
        
        position_count = len(context.portfolio.positions)
        # 当持有股票数量不足时：
        if g.stock_num > position_count and position_count != 0: # position_count != 0 用于避免第一次运行时代替go_trader 买入
            my_Trader(context) # 每月的选股逻辑，计算 g.choice
            cdata = get_current_data()
            psize = context.portfolio.available_cash/(g.stock_num - position_count)
            for s in g.choice:
                if s not in context.portfolio.positions:
                    order = order_value(s, psize) 
                    if len(context.portfolio.positions) == g.stock_num:
                        break

                
 
# 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list

# 过滤停牌股票
def filter_paused_stock(stock_list):
	current_data = get_current_data()
	return [stock for stock in stock_list if not current_data[stock].paused]


# 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
	current_data = get_current_data()
	return [stock for stock in stock_list
			if not current_data[stock].is_st
			and 'ST' not in current_data[stock].name
			and '*' not in current_data[stock].name
			and '退' not in current_data[stock].name]
#2-6 过滤次新股
def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=250)]


# 过滤涨幅过大的股票
def filter_limitup_stock(context, stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	current_data = get_current_data()
	
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] < current_data[stock].high_limit*0.97]

# 过滤跌幅过大的股票
def filter_limitdown_stock(context, stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	current_data = get_current_data()
	
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] > current_data[stock].low_limit*1.04]

#2-4 过滤股价高于10元的股票	
def filter_highprice_stock(context,stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] < 10]
						
def after_market_close(context):
    log.info(str(context.current_dt))
    
#4-2 如果no_trading_today_signal为True，则清仓
def close_account(context):
    if g.no_trading_today_signal == True:
        position_count = context.portfolio.positions
        if len(position_count) != 0:
            for stock in position_count:
                position = context.portfolio.positions[stock]
                close_position(position)
                log.info("卖出[%s]" % (stock))
                
                
                
#3-1 交易模块-自定义下单
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)

#3-2 交易模块-开仓
def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return True
    return False
                
                
#3-3 交易模块-平仓
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)  # 可能会因停牌失败
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False
    
    
#4-1 判断今天是否为账户资金再平衡的日期
def today_is_between(context, start_date, end_date):
    today = context.current_dt.strftime('%m-%d')
    if (start_date <= today) and (today <= end_date):
        return True
    else:
        return False
    # end