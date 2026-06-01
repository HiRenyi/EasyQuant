# 克隆自聚宽文章：https://www.joinquant.com/post/47208
# 标题：多品种ETF动量轮动+EPO优化
# 作者：openhe

# 克隆自聚宽文章：https://www.joinquant.com/post/47192
# 标题：分享一个低波动ETF轮动策略，近四年最大回撤14.26%
# 作者：hornor

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import talib
from scipy.optimize import minimize
import statsmodels.api as sm
from scipy.linalg import solve
#初始化函数 
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option('avoid_future_data', True)
    # 设置滑点为0 https://www.joinquant.com/view/community/detail/a31a822d1cfa7e83b1dda228d4562a70
    set_slippage(FixedSlippage(0))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0002, close_commission=0.0002, close_today_commission=0, min_commission=5), type='fund')
    # 过滤一定级别的日志
    log.set_level('system', 'error')
    
    g.stock_num = 3
    g._lambda = 10
    g.w = 0.2


    # 参数
    g.etf_pool = [
        # 商品
        '518880.XSHG',#黄金ETF
        '159985.XSHE',#豆粕ETF
        # 海外
        '513100.XSHG',#纳指ETF
        # 宽基
        '510300.XSHG',#沪深300ETF
        '159915.XSHE',#创业板
        # 窄基
        '159992.XSHE',#创新药ETF
        '515700.XSHG',#新能车ETF
        '510150.XSHG',#消费ETF
        '515790.XSHG',#光伏ETF
        '515880.XSHG',#通信ETF
        '512720.XSHG',#计算机ETF
        '512660.XSHG',#军工ETF
        '159740.XSHE',#恒生科技ETF
        ]	
    run_monthly(trade, 1, '9:30')
    # run_daily(trade, '9:30') #每天运行确保即时捕捉动量变化
    g.m_days = 34 #动量参考天数

#============基于年化收益和判定系数打分的动量因子轮动=============#
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
    df = df.dropna()
    rank_list = list(df.index)
    print (df)
    filtered_rank_list = [etf for etf in rank_list if df.loc[etf, 'score'] > 0]
    return filtered_rank_list
    #return rank_list   


def epo(x, signal, lambda_, method='simple', w=None, anchor=None, normalize=True, endogenous=True):
    n = x.shape[1]
    vcov = x.cov()
    corr = x.corr()
    I = np.eye(n)
    V = np.zeros((n, n))
    np.fill_diagonal(V, vcov.values.diagonal())
    std = np.sqrt(V)
    s = signal
    a = anchor

    shrunk_cor = ((1 - w) * I @ corr.values) + (w * I)  # equation 7
    cov_tilde = std @ shrunk_cor @ std  # topic 2.II: page 11
    inv_shrunk_cov = solve(cov_tilde, np.eye(n))

    if method == 'simple':
        epo = (1 / lambda_) * inv_shrunk_cov @ signal  # equation 16
    elif method == 'anchored':
        if endogenous:
            gamma = np.sqrt(a.T @ cov_tilde @ a) / np.sqrt(s.T @ inv_shrunk_cov @ cov_tilde @ inv_shrunk_cov @ s)
            epo = inv_shrunk_cov @ (((1 - w) * gamma * s) + ((w * I @ V @ a)))
        else:
            epo = inv_shrunk_cov @ (((1 - w) * (1 / lambda_) * s) + ((w * I @ V @ a)))

    if normalize:
        epo = [0 if a < 0 else a for a in epo]
        epo = epo / np.sum(epo)

    return epo

# 定义获取数据并调用优化函数的函数
def run_optimization(stocks, end_date):
    prices = get_price(stocks, count=1200, end_date=end_date, frequency='daily', fields=['close'])['close']
    returns = prices.pct_change().dropna() # 计算收益率
    d = np.diag(returns.cov())
    a = (1/d) / (1/d).sum()
    # a= np.array([0.25,0.25,0.25,0.25])
    weights = epo(x = returns, signal = returns.mean(), lambda_ = g._lambda, method = 'anchored', w = g.w, anchor=a)
    return weights
    
# 交易
def trade(context):
    end_date = context.previous_date 
    target_list = get_rank(g.etf_pool)[:g.stock_num]
    
    # 卖出
    hold_list = list(context.portfolio.positions)
    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)
            print( '卖出' + str(etf))
        else:
            print( '继续持有' + str(etf))
            
    # 买入
    weights = run_optimization(target_list, end_date)

    if weights is None:
        return
    total_value = context.portfolio.total_value 
    index = 0
    for w in weights:
        value = total_value * w 
        order_target_value(target_list[index], value) 
        index+=1   
