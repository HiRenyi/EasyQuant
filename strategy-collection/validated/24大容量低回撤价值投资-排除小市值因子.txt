# 克隆自聚宽文章：https://www.joinquant.com/post/47566
# 标题：大容量低回撤价值投资-排除小市值因子
# 作者：Ahfu

#导入函数库
from jqdata import *
from jqfactor import get_factor_values
from jqlib.technical_analysis import *
import numpy as np
import pandas as pd
import statsmodels.api as sm
import datetime as dt
from sklearn.preprocessing import MinMaxScaler

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
    # 设置交易成本万分之1.2，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.00012, close_commission=0.00012, close_today_commission=0, min_commission=5),type='stock')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    #初始化全局变量
    g.stock_num = 40
    g.limit_up_list = [] #记录持仓中涨停的股票
    g.hold_list = [] #当前持仓的全部股票
    g.history_hold_list = [] #过去一段时间内持仓过的股票
    g.not_buy_again_list = [] #最近买过且涨停过的股票一段时间内不再买入
    g.limit_days = 20 #不再买入的时间段天数
    g.target_list = [] #开盘前预操作股票池
    # 设置交易运行时间
    run_daily(prepare_stock_list, time='9:05', reference_security='000300.XSHG')
    run_monthly(adjust_position, 1, time='9:30', reference_security='000300.XSHG')
    run_daily(check_limit_up, time='14:00', reference_security='000300.XSHG') #检查持仓中的涨停股是否需要卖出
    run_monthly(print_position_info, 1, time='15:10', reference_security='000300.XSHG')

#1-2 选股模块
def get_stock_list(context):
    yesterday = str(context.previous_date)    
    end_date = context.previous_date
    last_days = end_date - timedelta(days=300)
    securities_df = get_all_securities(date=last_days)
    initial_list = securities_df.index.tolist()

    factor_values = get_factor_values(initial_list, [
        'roic_ttm', #投资资本回报率TTMv
        'gross_income_ratio', #销售毛利率
        'sales_to_price_ratio', #营收市值比	1 / ps_ratio (ttm)
        'Variance120', #120日年化收益方差
        ], end_date=yesterday, count=1)
    df = pd.DataFrame(index=initial_list, columns=factor_values.keys())
    df['roic_ttm'] = list(factor_values['roic_ttm'].T.iloc[:,0])
    df['gross_income_ratio'] = list(factor_values['gross_income_ratio'].T.iloc[:,0])
    df['sales_to_price_ratio'] = list(1/factor_values['sales_to_price_ratio'].T.iloc[:,0])
    df['Variance120'] = list(factor_values['Variance120'].T.iloc[:,0])
    df = df.dropna()

    # 归一化所有列
    scaler = MinMaxScaler()
    df2 = pd.DataFrame(scaler.fit_transform(df), columns=df.columns, index=df.index)
    df2['total_score'] = df2['roic_ttm'] + df2['gross_income_ratio'] - df2['sales_to_price_ratio'] - df2['Variance120']
    df2 = df2.sort_values(by=['total_score'], ascending=False)
    ms_list = list(df2.index)

    return ms_list

#1-3 准备股票池
def prepare_stock_list(context):
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
    #获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.high_limit_list = list(df.code)
    else:
        g.high_limit_list = []


#1-5 整体调整持仓
def adjust_position(context):
    if context.previous_date.month not in [1,4,7,10]:
        return
    # 获取应买入列表 
    g.target_list = get_stock_list(context)
    #截取不超过最大持仓数的股票量
    g.target_list = g.target_list[:min(g.stock_num, len(g.target_list))]
    #调仓卖出
    for stock in g.hold_list:
        if (stock not in g.target_list) and (stock not in g.high_limit_list):
            log.info("卖出[%s]" % (stock))
            position = context.portfolio.positions[stock]
            close_position(position)
        else:
            log.info("已持有[%s]" % (stock))
    #调仓买入
    position_count = len(context.portfolio.positions)
    target_num = len(g.target_list)
    if target_num > position_count:
        value = context.portfolio.cash / (target_num - position_count)
        for stock in g.target_list:
            if context.portfolio.positions[stock].total_amount == 0:
                if open_position(stock, value):
                    if len(context.portfolio.positions) == target_num:
                        break

#1-6 调整昨日涨停股票
def check_limit_up(context):
    now_time = context.current_dt
    if g.high_limit_list != []:
        #对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.high_limit_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0,0] < current_data.iloc[0,1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("[%s]涨停，继续持有" % (stock))

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

#4-1 打印每日持仓信息
def print_position_info(context):
	c = get_current_data()
	positions_dict = context.portfolio.positions
	for position in list(positions_dict.values()):
	    log.info("当前持仓：{0}:{1}, 市值：{2}, 盈利：{3}%, 建仓时间：{4}".format(c[position.security].name, position.security[:6], round(position.value,0), round((position.value-(position.avg_cost*position.total_amount))/(position.avg_cost*position.total_amount)*100,1), position.init_time))
	log.info('#########################################################################################\n\n')
