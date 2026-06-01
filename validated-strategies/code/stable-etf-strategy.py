# 克隆自聚宽文章：https://www.joinquant.com/post/48989
# 标题：稳健型ETF策略
# 作者：gjbdyrs

# 克隆自聚宽文章：https://www.joinquant.com/post/48355
# 标题：7年回测，胜率100%、年化7.88%、最大回撤5.86%
# 作者：东哥

import pandas as pd
import numpy as np
from jqdata import *
from jqlib.technical_analysis import *

#初始化，回测开始时执行
def initialize(context):
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 设置滑点 
    set_slippage(FixedSlippage(0.002))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0002, close_commission=0.0002, close_today_commission=0, min_commission=5), type='fund')
    # 过滤一定级别的日志
    log.set_level('system', 'error')

    #每周第1个交易日早盘时运行
    run_monthly(on_start,1,'9:35')
    


def on_start(context):
    #年度再平衡
    if year_start(context)==1:
        for s in context.portfolio.positions:
            order_target(s, 0)
    stocks=[]
    yesterday_macd = context.current_dt 
    macd_300 = get_macd_M('000300.XSHG',yesterday_macd)
    macd_100 = get_macd_M('513100.XSHG',yesterday_macd)
    macd_49 = get_macd_M('159949.XSHE',yesterday_macd)
    macd_88 = get_macd_M('518880.XSHG',yesterday_macd)
    #1
    if macd_49>0:
        g.stock_fund_1 = '159949.XSHE' #创业板50
    else:
        if macd_100>0:
            g.stock_fund_1 ='513100.XSHG'#纳斯达克
        else:
            if get_zf(context)>-6:
                g.stock_fund_1 ='510880.XSHG'#红利
            else:
                g.stock_fund_1 ='511010.XSHG' #国债ETF 
    #2            
    if get_zf(context)>-6:
        g.stock_fund_2 ='510880.XSHG'#红利
    else:
        g.stock_fund_2 ='511010.XSHG' #国债ETF 
    #3            
    if macd_88>0:
        g.stock_fund_3 = '518880.XSHG' #黄金
    else:
        if macd_300>0 and get_zf(context)>-6:
            g.stock_fund_3 ='510880.XSHG'#红利
        else:
            g.stock_fund_3 = '518880.XSHG' #黄金
    #4
    g.stock_fund_4 = "511010.XSHG" #国债ETF        
    #5
    g.stock_fund_5 = "511880.XSHG" #银华日利     

    stocks.append(g.stock_fund_1)
    stocks.append(g.stock_fund_2)
    stocks.append(g.stock_fund_3)
    stocks.append(g.stock_fund_4)
    stocks.append(g.stock_fund_5)
    cdata = get_current_data()
    #初始建仓（如果当前为空仓则建仓）
    if context.portfolio.total_value == context.portfolio.available_cash :
        amount=[]
        cash=context.portfolio.available_cash
        amount_in=math.floor(cash*0.125/cdata[g.stock_fund_1].last_price/100)*100
        order(g.stock_fund_1,amount_in)
        amount.append(amount_in)
        
        amount_in=math.floor(cash*0.125/cdata[g.stock_fund_2].last_price/100)*100
        order(g.stock_fund_2,amount_in)
        amount.append(amount_in)
        
        amount_in=math.floor(cash*0.25/cdata[g.stock_fund_3].last_price/100)*100
        order(g.stock_fund_3,amount_in)
        amount.append(amount_in)
        
        amount_in=math.floor(cash*0.25/cdata[g.stock_fund_4].last_price/100)*100
        order(g.stock_fund_4,amount_in)
        amount.append(amount_in)
        
        amount_in=math.floor(cash*0.25/cdata[g.stock_fund_5].last_price/100)*100
        order(g.stock_fund_5,amount_in)
        amount.append(amount_in)
        g.total_amount=amount
        g.stock_fund=stocks
        return
    # Sell
    if g.stock_fund[0]!=g.stock_fund_1:
        order(g.stock_fund[0],-g.total_amount[0])
        amount_in=math.floor(context.portfolio.cash/cdata[g.stock_fund_1].last_price/100)*100
        order(g.stock_fund_1, amount_in)   
        g.total_amount[0]=amount_in
        
    if g.stock_fund[1]!=g.stock_fund_2:
        order(g.stock_fund[1],-g.total_amount[1])
        amount_in=math.floor(context.portfolio.cash/cdata[g.stock_fund_2].last_price/100)*100
        order(g.stock_fund_2, amount_in)   
        g.total_amount[1]=amount_in
        
    if g.stock_fund[2]!=g.stock_fund_3:
        order(g.stock_fund[2],-g.total_amount[2])
        amount_in=math.floor(context.portfolio.cash/cdata[g.stock_fund_3].last_price/100)*100
        order(g.stock_fund_3, amount_in)   
        g.total_amount[2]=amount_in
    g.stock_fund=stocks
    
#macd
def get_macd_M(stock,check_date):
    # 计算并输出 security_list1 的 MACD 值
    macd_dif, macd_dea, macd_macd = MACD(stock,check_date=check_date, SHORT = 12, LONG = 26, MID = 9,unit = '1M',include_now=False)
    macd_list =macd_macd[stock]
    return macd_list    
#第一个交易日
def year_start(context):
    # 回测当前时间获取
    year= context.current_dt.year
    month = context.current_dt.month
    day = context.current_dt.day
    # 获取该年份的所有交易日
    trade_days = get_trade_days(start_date=str(year) + '-01-01', end_date=str(year) + '-12-31')
    # 返回第一个交易日
    trade_days=trade_days[0]
    trade_days=trade_days.day
    star=0
    if month==1 and day==trade_days:
        star=1
    return star
# etf年度收益
def get_zf(context):
    etf='510880.XSHG'
    year= context.current_dt.year
    start_dateold = datetime.datetime(year-1,12,20).strftime('%Y-%m-%d')
    end_dateold = datetime.datetime(year-1,12,31).strftime('%Y-%m-%d')
    df_ALL = attribute_history(etf, 25, '1d', ['close'])
    #前一天收盘价
    dfclose=df_ALL.close
    df=dfclose[-1]
    #去年收盘价
    dfold= get_price(etf,start_date=start_dateold, end_date=end_dateold, frequency='1d',panel=False)
    dfold=dfold.close
    dfold=dfold[-1]
    zf=round((df-dfold)*100 /dfold,2)
    return zf
