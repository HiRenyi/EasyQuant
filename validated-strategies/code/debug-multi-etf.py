# 克隆自聚宽文章：https://www.joinquant.com/post/48875
# 标题：Debug-输出信息-多标的版ETF策略(ETF复现之三）
# 作者：璐璐202006

'''
买入规则：
5日均线大于20日均线 。
最近20个交易日的涨幅大于5% 。
最近20个交易日的涨幅小于20%。
从符合上述条件的ETF中，按涨幅从高到低排序，选择前g.etf_num个进行买入。
卖出规则：
当前持有的ETF不在最近20个交易日涨幅排名前g.rank_num的ETF中。
当前持有的ETF涨幅超过20%。
卖出后不立即买入已经卖出的ETF（通过检查是否在g.buy_etf列表中）。
'''


import pandas as pd
import talib
from jqdata import *

def initialize(context):
    set_option('avoid_future_data', True)
    set_benchmark('513100.XSHG')
    set_option('use_real_price', True)
    g.etf = [
        '516510.XSHG', # 云计算(信息技术)
        '159985.XSHE',  # 豆粕
        '515880.XSHG', # 通讯
        '513060.XSHG', #恒生医疗
        '512660.XSHG', # 军工(军工)
        '513520.XSHG', # 日经
        '513330.XSHG',# 恒生互联网
        '515790.XSHG', # 光伏
        '512100.XSHG', # 中证1000   
        '512100.XSHG', # 中证500         
        '159998.XSHE', # 计算机
        '513500.XSHG', # 标普500 
        '162719.XSHE',# 石油LOF
        '159949.XSHE',# 创业板50
        '515030.XSHG',#新能车
        '159928.XSHE', # 消费 (消费)
        '513100.XSHG', # 纳指100
        '159995.XSHE',# 芯片
    ]
    g.etf_num = 2  # ETF持仓数量
    g.change_day = 1  # 轮动天数
    g.day = 0
    g.min_inc = 0.05  # 涨幅最少值
    g.max_inc = 0.2  # 涨幅最大值
    g.rank_num = 4  # 排名数
    g.longdays = 20  # 长均线天数
    g.shortdays = 5  # 短均线天数
    g.buy_etf = []
    g.sell_etf = []
    run_daily(check_etf, "09:25")
    run_daily(check_etf_2, "9:30")
    run_daily(trade, "9:30")

    g.order_info_dict = {}
    run_daily(print_position_info, '15:10')
    g.previous_portfolio_value = context.portfolio.starting_cash 
    
def calculate_etf_metrics(etf_list, long_days, short_days):
    malong = []
    mashort = []
    inclong = []
    for etf in etf_list:
        df = attribute_history(etf, long_days)
        inclong.append((df['close'][-1] / df['close'][0] - 1))
        malong.append(df['close'].mean())
        mashort.append(df['close'].tail(short_days).mean())
    
    d = {'inc': inclong, 'malong': malong, 'mashort': mashort}
    df = pd.DataFrame(data=d, index=etf_list)
    return df

def check_etf(context):
    df = calculate_etf_metrics(g.etf, g.longdays, g.shortdays)
    df = df.sort_values(by='inc', ascending=False)
    df1 = df[(df['mashort'] > df['malong']) & (df['inc'] > g.min_inc) & (df['inc'] < g.max_inc)]
    g.buy_etf = list(df1.index)[:g.etf_num]
    g.sell_etf = []
    rank_etf = list(df.index)[:g.rank_num]
    for etf in list(context.portfolio.positions):
        if etf not in rank_etf or (df['inc'][etf] > g.max_inc).any():
            if etf not in g.buy_etf:
                g.sell_etf.append(etf)
        if etf in g.buy_etf and etf not in g.sell_etf:
            g.buy_etf.remove(etf)
def check_etf_2(context):
    df = calculate_etf_metrics(g.etf, g.longdays, g.shortdays)
    df = df.sort_values(by='inc', ascending=False)
    
    log.info("——————————————————————————————————")
    for i in range(len(df)):
        etf = df.index[i]
        name = get_security_info(etf).display_name
        mashort_value = float(df.iloc[i]['mashort'])
        malong_value = float(df.iloc[i]['malong'])
        inc_value = float(df.iloc[i]['inc'])
        log.info("{}. {}，5日均线：{:.2f}，20日均线：{:.2f}，20日涨幅：{:.2%}".format(
            i + 1,
            name,
            mashort_value,
            malong_value,
            inc_value
        ))
    log.info("——————————————————————————————————")
    
def trade(context):
    if g.day % g.change_day == 0:
        check_etf(context)
        for etf in g.sell_etf:
            order_target_value(etf, 0)
        position_count = len(context.portfolio.positions)
        if g.etf_num > position_count:
            cash = context.portfolio.available_cash / (g.etf_num - position_count)
            for etf in g.buy_etf:
                order_target_value(etf, cash)
                if len(context.portfolio.positions) == g.etf_num:
                    break
    g.day += 1

def print_position_info(context):
    log.info("——————————————————————————————————")
    print('证券名称\t买入日期\t买入价格\t现价\t持仓收益率')
    for position in list(context.portfolio.positions.values()):
        security = position.security
        name = get_security_info(security).display_name
        order_info = {}
        order_info['security'] = name
        order_info['买入日期'] = position.init_time.date()
        order_info['买入价格'] = position.avg_cost
        order_info['现价'] = position.price
        order_info['持仓收益率'] = (position.price / position.avg_cost - 1) * 100
        key = '{}:{}'.format(order_info['买入日期'], name)
        g.order_info_dict[key] = order_info
        print('{:<0}\t{}\t{:.2f}\t{:.2f}\t{:.2f}%'.format(
            order_info['security'],
            order_info['买入日期'],
            order_info['买入价格'],
            order_info['现价'],
            order_info['持仓收益率']
        ))
    log.info("——————————————————————————————————")
    # 计算累计总收益率
    g.total_return_rate = (context.portfolio.portfolio_value - context.portfolio.starting_cash) / context.portfolio.starting_cash * 100
    print('累计收益率={:.2f}%'.format(g.total_return_rate))
    
    # 计算并输出今日持仓收益率
    if g.previous_portfolio_value:
        daily_return_rate = (context.portfolio.portfolio_value / g.previous_portfolio_value - 1) * 100
        print('今日收益率={:.2f}%'.format(daily_return_rate))
    
    # 保存当前的投资组合价值以供下次计算使用
    g.previous_portfolio_value = context.portfolio.portfolio_value

    log.info("——————————————————————————————————")