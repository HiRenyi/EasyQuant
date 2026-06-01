from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd



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
    #初始化全局变量
    g.no_trading_today_signal = False
    g.stock_num = 1
    g.hold_list = [] #当前持仓的全部股票    
    g.yesterday_HL_list = [] #记录持仓中昨日涨停的股票
    g.factor_list = [
        (#ARBR-SGAI-NPtTORttm-RPps
            [
                'ARBR', #情绪类因子 ARBR
                'SGAI', #质量类因子 销售管理费用指数
                'net_profit_to_total_operate_revenue_ttm', #质量类因子 净利润与营业总收入之比
                'retained_profit_per_share' #每股指标因子 每股未分配利润
            ],
[-3.894481386287797e-19, 6.051549381361553e-05,-0.00013489470173496827,
 -0.0006228721291235472]
        ),
        (#P1Y-TPtCR-VOL120
            [
                'Price1Y', #动量类因子 当前股价除以过去一年股价均值再减1
                'total_profit_to_cost_ratio', #质量类因子 成本费用利润率
                'VOL120' #情绪类因子 120日平均换手率
            ],
[-0.007686604605324844 ,-0.001064082235156668 ,-0.0006372186835828526]
        ),
        (#PNF-TPtCR-ITR
            [
                'price_no_fq', #技术指标因子 不复权价格因子
                'total_profit_to_cost_ratio', #质量类因子 成本费用利润率
                'inventory_turnover_rate' #质量类因子 存货周转率
            ],
[-0.00022239096483198066, -0.0003400190412564607, -1.2360751761544718e-08]
        ),
        (#DtA-OCtORR-DAVOL20-PNF-SG
            [
                'debt_to_assets', #风格因子 资产负债率
                'operating_cost_to_operating_revenue_ratio', #质量类因子 销售成本率
                'DAVOL20', #情绪类因子 20日平均换手率与120日平均换手率之比
                'price_no_fq', #技术指标因子 不复权价格因子
                'sales_growth' #风格因子 5年营业收入增长率
            ],
[-0.0013461722141220884, 0.001285717224773847, -0.003021350121015241,
 -0.00023334854089909846, 0.0002343967416749908]
        ),
        (#TVSTD6-CFpsttm-SR120-NONPttm
            [
                'TVSTD6', #情绪类因子 6日成交金额的标准差
                'cashflow_per_share_ttm', #每股指标因子 每股现金流量净额
                'sharpe_ratio_120', #风险类因子 120日夏普率
                'non_operating_net_profit_ttm' #基础科目及衍生类因子 营业外收支净额TTM
            ],
[-6.694922635779981e-11 ,-0.00016142377647805555 ,-0.0005529870175398643,
 9.167393894186556e-12]
        )
    ]
    # 设置交易运行时间
    run_daily(prepare_stock_list, '9:05')
    run_weekly(weekly_adjustment, 1, '9:30')
    run_daily(check_limit_up, '14:00') #检查持仓中的涨停股是否需要卖出
    run_daily(close_account, '14:30')
    run_daily(print_position_info, '15:10')



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
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    final_list = []
    #MS
    for factor_list,coef_list in g.factor_list:
        factor_values = get_factor_values(initial_list,factor_list, end_date=yesterday, count=1)
        df = pd.DataFrame(index=initial_list, columns=factor_values.keys())
        for i in range(len(factor_list)):
            df[factor_list[i]] = list(factor_values[factor_list[i]].T.iloc[:,0])
        df = df.dropna()
        df['total_score'] = 0
        for i in range(len(factor_list)):
            df['total_score'] += coef_list[i]*df[factor_list[i]]
        df = df.sort_values(by=['total_score'], ascending=False) #分数越高即预测未来收益越高，排序默认降序
        complex_factor_list = list(df.index)[:int(0.1*len(list(df.index)))]
        q = query(valuation.code,valuation.circulating_market_cap,indicator.eps).filter(valuation.code.in_(complex_factor_list)).order_by(valuation.circulating_market_cap.asc())
        df = get_fundamentals(q)
        df = df[df['eps']>0]
        lst  = list(df.code)
        lst = filter_paused_stock(lst)
        lst = filter_limitup_stock(context, lst)
        lst = filter_limitdown_stock(context, lst)
        lst = lst[:min(g.stock_num, len(lst))]
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



#2-1 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

#2-2 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]

#2-3 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list

#2-4 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] <    current_data[stock].high_limit]

#2-5 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]

#2-6 过滤次新股
def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date <    datetime.timedelta(days=375)]



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