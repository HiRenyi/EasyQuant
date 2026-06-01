# 克隆自聚宽文章：https://www.joinquant.com/post/49537
# 标题：趋势筛选后相关性最小etf轮动-加速10倍版
# 作者：蚂蚁量化

'''
回测程序来源：
# 克隆自聚宽文章：https://www.joinquant.com/post/49303
# 标题：相关性最小etf轮动
# 作者：开心果

eft池来源：
# 克隆自聚宽文章：ttps://www.joinquant.com/view/community/detail/cd4f11534d06711f53b4bad1f5105f09?type=1
# 标题：手把手教你构建ETF策略候选池
# 作者：JoelZ

# 本人修改：
# 1. 添加了函数, 从历史数据中筛选维持多头趋势性较强的品种
# 2. 添加了'score'的上下限-0.5<'score'<4.5，避免买入过强或过弱的etf

'''
import numpy as np
import pandas as pd
#初始化函数 
def initialize(context):
    set_slippage(FixedSlippage(0.02),type='stock')   # 为股票设定滑点为百分比滑点     set_slippage(PriceRelatedSlippage(0.00246),type='stock')
    set_slippage(FixedSlippage(0.002),type='fund')   # 为股票设定滑点为百分比滑点     set_slippage(PriceRelatedSlippage(0.00246),type='stock')

    
    # 设置交易成本
    set_order_cost(OrderCost( open_tax=0.0, close_tax=0.0, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='fund')
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    log.set_level('system', 'error')
    g.etf_pool = ['512660.XSHG', '510880.XSHG', '159915.XSHE', '513050.XSHG', '510050.XSHG', '588100.XSHG', '512100.XSHG', '518800.XSHG', '513060.XSHG', '511010.XSHG', '512980.XSHG', '512010.XSHG', '513100.XSHG', '512720.XSHG', 
                    '512070.XSHG', '515880.XSHG', '159920.XSHE', '159922.XSHE', '513520.XSHG', '515000.XSHG', '515790.XSHG', '515700.XSHG', '159825.XSHE', '512400.XSHG', '512200.XSHG', '513360.XSHG', '512480.XSHG', '510230.XSHG', '159647.XSHE', '159928.XSHE']
    g.m_days = 25 
    up_strength(context)
    run_daily(trade, '10:00')
    run_monthly(up_strength, 1, "9:00")


def min_corr(stocks):
    nday = 243
    p = history(nday, '1d', 'close', stocks).dropna(axis=1)
    r = np.log(p).diff()[1:]
    m_corr = r.corr()
    corr_mean = {}
    for stock in m_corr.columns:
        corr_mean[stock] = m_corr[stock].abs().mean()
    etf_pool = sorted(corr_mean, key=corr_mean.get)[:4]
    return etf_pool

def get_rank(etf_pool):
    score_list = []
    for etf in etf_pool:
        df = attribute_history(etf, g.m_days, '1d', ['close'])
        y = df['log'] = np.log(df.close)
        x = df['num'] = np.arange(df.log.size)
        slope, intercept = np.polyfit(x, y, 1)
        annualized_returns = math.pow(math.exp(slope), 250) - 1
        r_squared = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
        score = annualized_returns * r_squared
        score_list.append(score)
    df = pd.DataFrame(index=etf_pool, data={'score':score_list})
    df = df.sort_values(by='score', ascending=False)
    df = df[(df['score']>-0.5) & (df['score']<4.5)]
    rank_list = list(df.index)

    return rank_list

    
# 交易
def up_strength(context):
    g.trend_length_ranking = get_trend_length(g.etf_pool, 3)

    
# 交易
def trade(context):
    target_num = 1
    etf_pool = min_corr(g.trend_length_ranking)
    target_list = get_rank(etf_pool)[:target_num]
        
    # 卖出    
    hold_list = list(context.portfolio.positions)
    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)
    # 买入
    hold_list = list(context.portfolio.positions)
    if len(hold_list) < target_num:
        value = context.portfolio.available_cash / (target_num - len(hold_list))
        for etf in target_list:
            if context.portfolio.positions[etf].total_amount == 0:
                order_target_value(etf, value)
    hold_list = list(context.portfolio.positions)
    if hold_list:
        print(f'- 持有:  {mingcheng(hold_list[0])}, {hold_list[0]}')

# ####################################################################
# 本人添加程序

def calculate_ma(data, window):
    return data.rolling(window=window).mean()

def count_days_above(data, short_window, long_window):
    # 计算短期和长期均线
    short_ma = calculate_ma(data, short_window)
    long_ma = calculate_ma(data, long_window)

    # 初始化计数器
    count = 0
    total_days = 0

    for i in range(long_window, len(data)):
        if short_ma[i] > long_ma[i]:
            if i == long_window or short_ma[i-1] <= long_ma[i-1]:
                # 如果是突破点，则重置计数器
                count = 0
            count += 1
        else:
            # 如果短期均线跌落到长期均线下方，则结束计数
            count = 0

        if count > 0:
            total_days += count

    return total_days / (len(data) - long_window)

# 假设df是一个包含所有股票历史数据的DataFrame，
def get_trend_length(etf_pool, limit):
    df = history(3500, unit='1d', field='close', security_list=etf_pool, df=True, skip_paused=True, fq='pre')

    stocks_data = {stock:df[stock] for stock in df.columns}

    # 短期和长期均线窗口
    short_window = 10
    long_window = 30

    # 统计每只股票的数据
    results = {stock: count_days_above(data, short_window, long_window) for stock, data in stocks_data.items()}
    results = {stock:results[stock] for stock in results if results[stock]>limit}
    # 按平均天数降序排序
    # sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
    return list(results.keys())   #sorted_results


def mingcheng(stock):
    try:
        return get_security_info(stock).display_name
    except:
        return "还未上市"

