# 克隆自聚宽文章：https://www.joinquant.com/post/44699
# 标题：10年52倍，年化59%，全新因子方法超稳定
# 作者：小白F

#导入函数库
from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd

industry_code = ['HY001', 'HY002', 'HY003', 'HY004', 'HY005', 'HY006', 'HY007', 'HY008', 'HY009', 'HY010', 'HY011']

#初始化函数 
def initialize(context):
    # 设定基准
    set_benchmark('000905.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5),type='stock')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    log.set_level('system', 'error') 
    #初始化全局变量
    g.no_trading_today_signal = False
    g.stock_num = 3
    g.hold_list = [] #当前持仓的全部股票    
    g.yesterday_HL_list = [] #记录持仓中昨日涨停的股票
    
    
    g.factor_list = [
        {'ARBR': (-0.9996444781983547, 0.9986148448690932)}
        ]
   
    g.chosen_factor = ['ARBR']
    g.month_day = 1

    
    # 设置交易运行时间
    run_daily(prepare_stock_list, '9:05')
    run_weekly(weekly_adjustment,g.month_day, '9:30')
    
    run_daily(check_limit_up, '14:00') #检查持仓中的涨停股是否需要卖出
    run_daily(close_account, '14:30')
    # run_daily(print_position_info, '15:10')


#1-1 准备股票池
def prepare_stock_list(context):
    #获取已持有列表
    g.hold_list= []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    #获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
    #判断今天是否为账户资金再平衡的日期
    g.no_trading_today_signal = today_is_between(context, '04-05', '04-30')
    
#1-2 选股模块
def get_stock_list(context):
    #指定日期防止未来数据
    yesterday = context.previous_date
    today = context.current_dt
    #获取初始列表
    initial_list = get_all_securities('stock', today).index.tolist()
    initial_list = filter_all_stock2(context, initial_list)
    final_list = []
    #MS
    factor_list = list(g.factor_list[0].keys())
    # print(factor_list)
    factor_data = get_factor_values(initial_list,factor_list, end_date=yesterday, count=1)
    df_jq_factor_value = pd.DataFrame(index=initial_list, columns=factor_list)
    for factor in factor_list:
        df_jq_factor_value[factor] = list(factor_data[factor].T.iloc[:,0])

    #print('before:df_jq_factor_value is \n%s'% df_jq_factor_value)
    df_jq_factor_value = data_preprocessing(df_jq_factor_value,initial_list,industry_code,yesterday) #标准化
    #print('after:df_jq_factor_value is \n%s'% df_jq_factor_value)
    #print('df_jq_factor_value.info is \n%s'% df_jq_factor_value.info)
    # tar = g.model.predict_proba(df_jq_factor_value)

    df = df_jq_factor_value
    df = df.dropna()
    for factor in g.chosen_factor :
        # print(df[factor_list[i]],factor_value[i][0])
        df = df[(df[factor]>=g.factor_list[0][factor][0]) & (df[factor]<=g.factor_list[0][factor][1])]
        print(f'过滤完 {factor} ，剩余：{len(df)}')
        
    # df['total_score'] = list(tar[:,1])
    # df = df.sort_values(by=['total_score'], ascending=False) #分数越高即预测未来收益越高，排序默认降序
    # postive_list = list(df.index)[:int(0.1*len(list(df.index)))]
    postive_list = list(df.index)
    log.info(f'因子筛选后的数量：{len(postive_list)}/{len(df)}')
    # negative_list = list(df.index)[int(0.3*len(list(df.index))):-1]
    q = query(valuation.code,valuation.circulating_market_cap,indicator.eps).filter(valuation.code.in_(postive_list)).order_by(valuation.circulating_market_cap.asc())
    # q = query(valuation.code,valuation.circulating_market_cap,indicator.eps).filter(valuation.code.in_(postive_list)).order_by(indicator.eps.desc())

    df2 = get_fundamentals(q)
    df2 = df2[df2['eps']>0]
    lst  = list(df2.code)

    lst = lst[:min(g.stock_num, len(lst))]
    # df['chosen'] = str(lst)
    # log.info(df[['total_score', 'chosen']].head(6))
    for stock in lst:
        if stock not in final_list:
            final_list.append(stock)
    return final_list

#1-3 整体调整持仓
def weekly_adjustment(context):
    if g.no_trading_today_signal == False:
        #获取应买入列表 
        target_list = get_stock_list(context)
        #调仓卖出
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.yesterday_HL_list):
                log.info("卖出[%s]" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("已持有[%s]" % (stock))
        #调仓买入
        position_count = len(context.portfolio.positions)
        target_num = len(target_list)
        if target_num > position_count:
            value = context.portfolio.cash / (target_num - position_count)
            for stock in target_list:
                if context.portfolio.positions[stock].total_amount == 0:
                    if open_position(stock, value):
                        if len(context.portfolio.positions) == target_num:
                            break

#1-4 调整昨日涨停股票
def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        #对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.yesterday_HL_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0,0] <    current_data.iloc[0,1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("[%s]涨停，继续持有" % (stock))


# 过滤股票，过滤停牌退市ST股票，选股时使用
def filter_all_stock2(context, stock_list):
    # 过滤次新股（新股、老股的分界日期，两种指定方法）
    # 新老股的分界日期, 自然日180天
    # by_date = context.previous_date - datetime.timedelta(days=180)
    # 新老股的分界日期，120个交易日
    by_date = get_trade_days(end_date=context.previous_date, count=252)[0]
    all_stocks = get_all_securities(date=by_date).index.tolist()
    stock_list = list(set(stock_list).intersection(set(all_stocks)))

    curr_data = get_current_data()
    return [stock for stock in stock_list if not (
            stock.startswith(('3', '68', '4', '8')) or  # 创业，科创，北交所
            curr_data[stock].paused or # 停牌
            curr_data[stock].is_st or  # ST
            ('ST' in curr_data[stock].name) or # ST
            ('*' in curr_data[stock].name) or # 退市 
            ('退' in curr_data[stock].name) or # 退市
            (curr_data[stock].day_open == curr_data[stock].high_limit) or  # 涨停开盘, 其它时间用last_price
            (curr_data[stock].day_open == curr_data[stock].low_limit)  # 跌停开盘, 其它时间用last_price
    )]


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

#4-2 清仓后次日资金可转
def close_account(context):
    if g.no_trading_today_signal == True:
        if len(g.hold_list) != 0:
            for stock in g.hold_list:
                position = context.portfolio.positions[stock]
                close_position(position)
                log.info("卖出[%s]" % (stock))

#4-3 打印每日持仓信息
def print_position_info(context):
    #打印当天成交记录
    trades = get_trades()
    for _trade in trades.values():
        print('成交记录：'+str(_trade))
    #打印账户信息
    for position in list(context.portfolio.positions.values()):
        securities=position.security
        cost=position.avg_cost
        price=position.price
        ret=100*(price/cost-1)
        value=position.value
        amount=position.total_amount    
        print('代码:{}'.format(securities))
        print('成本价:{}'.format(format(cost,'.2f')))
        print('现价:{}'.format(price))
        print('收益率:{}%'.format(format(ret,'.2f')))
        print('持仓(股):{}'.format(amount))
        print('市值:{}'.format(format(value,'.2f')))
        print('———————————————————————————————————')
    print('———————————————————————————————————————分割线————————————————————————————————————————')
    
    
    #取股票对应行业
def get_industry_name(i_Constituent_Stocks, value):
    return [k for k, v in i_Constituent_Stocks.items() if value in v]

#缺失值处理
def replace_nan_indu(factor_data,stockList,industry_code,date):
    #把nan用行业平均值代替，依然会有nan，此时用所有股票平均值代替
    i_Constituent_Stocks={}
    data_temp=pd.DataFrame(index=industry_code,columns=factor_data.columns)
    for i in industry_code:
        temp = get_industry_stocks(i, date)
        i_Constituent_Stocks[i] = list(set(temp).intersection(set(stockList)))
        data_temp.loc[i]=mean(factor_data.loc[i_Constituent_Stocks[i],:])
    for factor in data_temp.columns:
        #行业缺失值用所有行业平均值代替
        null_industry=list(data_temp.loc[pd.isnull(data_temp[factor]),factor].keys())
        for i in null_industry:
            data_temp.loc[i,factor]=mean(data_temp[factor])
        null_stock=list(factor_data.loc[pd.isnull(factor_data[factor]),factor].keys())
        for i in null_stock:
            industry=get_industry_name(i_Constituent_Stocks, i)
            if industry:
                factor_data.loc[i,factor]=data_temp.loc[industry[0],factor] 
            else:
                factor_data.loc[i,factor]=mean(factor_data[factor])
    return factor_data

#数据预处理
def data_preprocessing(factor_data,stockList,industry_code,date):
    #去极值
    factor_data = winsorize_med(factor_data, scale=5, inf2nan=False,axis=0)
    #缺失值处理
    factor_data = replace_nan_indu(factor_data,stockList,industry_code,date)
    #标准化处理
    factor_data = standardlize(factor_data,axis=0)
    
    return factor_data