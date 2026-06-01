# 克隆自聚宽文章：https://www.joinquant.com/post/45272
# 标题：基于Gyro^.^大神的小市值策略的因子匹配研究
# 作者：热情的刀

# 克隆自聚宽文章：https://www.joinquant.com/post/44563
# 标题：微盘股研究
# 作者：Gyro^.^

import pandas as pd
from jqdata import *

def initialize(context):
    # 设置系统
    log.set_level('order', 'error') 
    set_option('use_real_price', True) 
    set_option('avoid_future_data', True) 
    g.days = 0 


def after_code_changed(context):
    # 设置策略
    unschedule_all()
    run_daily(iUpdate, time='before_open') 
    run_daily(iTrader, time='9:35') 
    run_daily(iReport, time='after_close') 
    
#获取指定间隔的交易日的日期
def get_previous_trade_day(current_date, n):
    # 获取交易日历
    trade_day = get_trade_days(end_date=current_date, count=n+1)[0]    
    return trade_day

#函数，将传入的列表中去掉极值
def drop_outlier(data_list):
    data_list.sort()
    #print('data_list1'+str(data_list))
    q1 = data_list[int(len(data_list) / 4)]
    q3 = data_list[int(len(data_list) * 3 / 4)]
    iqr = q3 - q1
    low = q1 - 1.5 * iqr
    high = q3 + 1.5 * iqr
    data_list = [x for x in data_list if x >= low and x <= high]
    #print('data_list2'+str(data_list))
    return data_list

#函数 将传入的列表中的值等分成10份，并返回一个
def divide_list_into_10(data_list):
    # 按升序排序列表
    data_list.sort()
    #print('data_list1'+str(data_list))
    # 确定每一份的大小
    chunk_size = len(data_list) // 10
    # 划分列表成为10等份
    lst_of_chunks = [data_list[i:i+chunk_size] for i in range(0, len(data_list), chunk_size)]
    # 返回每个部分的最小值
    result_list = [min(chunk) for chunk in lst_of_chunks]
    #print('data_list2'+str(result_list))
    return result_list    

def iUpdate(context):
    # 参数
    nchoice = 10
    nposition = 5
    # 全部A股
    dt_last = context.previous_date
    all_stock = get_all_securities('stock', dt_last)
    
    # 过滤ST
    cdata = get_current_data()
    stocks = [s for s in all_stock.index if not cdata[s].is_st]
    
    #过滤68,8,900
    stocks=[stock for stock in stocks if not stock.startswith('8') and not stock.startswith('688') and not stock.startswith('9')]
    
    #获取上一个交易日的日期
    previous_trade_day = get_previous_trade_day(context.current_dt, 1)
    #获取上个交易日的因子信息
    valuation_df = get_fundamentals(query(
                valuation.code,
                #换手率
                valuation.turnover_ratio,
                #流通股本
                valuation.circulating_cap,
                #总股本
                valuation.capitalization,
                #流通市值
                valuation.circulating_market_cap,
                #roe
                indicator.roe,
                #pe TTM
                valuation.pe_ratio
            ).filter(
                # 
                valuation.code.in_(stocks)
                
            ), date=previous_trade_day).dropna().set_index('code')
    
    #获取因子的列表        
    circulating_cap_factor_list=valuation_df['circulating_cap'].tolist()
    # print('turnover_ratio_list1'+str(turnover_ratio_list))
    #去极值
    circulating_cap_factor_list=drop_outlier(circulating_cap_factor_list)
    #print('turnover_ratio_list2'+str(turnover_ratio_list))
    #分成十份
    circulating_cap_factor_list=divide_list_into_10(circulating_cap_factor_list)
    #print('turnover_ratio_list3'+str(turnover_ratio_list))
    
    
    # 小盘股
    df = get_fundamentals(query(
            valuation.code,
            valuation.market_cap,
        ).filter(
            valuation.code.in_(stocks),
            valuation.pb_ratio > 0,
            valuation.circulating_cap > circulating_cap_factor_list[0],
            valuation.circulating_cap < circulating_cap_factor_list[1],
            indicator.roe>0,
            indicator.roa>0.45,
        ).order_by(valuation.market_cap.asc()
        ).limit(nchoice)
        ).dropna().set_index('code')
    # 结果
    g.choice = df.index.tolist()
    print(g.choice)
    g.position_size = 1.0/nposition * context.portfolio.total_value

def iTrader(context):
    # 参量
    choice = g.choice 
    position_size = g.position_size 
    lm_value = 0.8 * position_size 
    hm_value = 1.2 * position_size 
    cdata = get_current_data() 
    # 卖出
    for s in context.portfolio.positions:
        if cdata[s].paused or \
            cdata[s].last_price >= cdata[s].high_limit or \
            cdata[s].last_price <= cdata[s].low_limit:
            continue # 过滤三停
        if s not in choice:
            log.info('sell', s, cdata[s].name)
            order_target(s, 0, MarketOrderStyle(0.99*cdata[s].last_price))
    # 买进
    for s in choice:
        if context.portfolio.available_cash < position_size:
            break
        if cdata[s].paused or \
            cdata[s].last_price >= cdata[s].high_limit or \
            cdata[s].last_price <= cdata[s].low_limit:
            continue # 过滤三停
        if s not in context.portfolio.positions:
            log.info('buy', s, cdata[s].name)
            order_target_value(s, position_size, MarketOrderStyle(1.01*cdata[s].last_price))
        elif context.portfolio.positions[s].value < lm_value:
            log.info('balance+', s, cdata[s].name)
            order_target_value(s, position_size, MarketOrderStyle(1.01*cdata[s].last_price))
        elif context.portfolio.positions[s].value > hm_value:
            log.info('balance-', s, cdata[s].name)
            order_target_value(s, position_size, MarketOrderStyle(0.99*cdata[s].last_price))

def iReport(context):
    # 报告状态
    g.days = g.days + 1
    log.info('  positions', len(context.portfolio.positions))
    log.info('  return %.2f', 100*context.portfolio.returns)
    log.info('  cash %.2f',   context.portfolio.available_cash/10000)
    log.info('  value %.2f',  context.portfolio.total_value/10000)
    log.info('running days', g.days)
# end