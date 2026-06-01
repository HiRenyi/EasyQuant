# 克隆自聚宽文章：https://www.joinquant.com/post/46429
# 标题：搞市场最靓的仔！指数ETF动量轮动策略-2
# 作者：野蛮生涨

# 导入函数库
from jqdata import *
import random

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    set_option("avoid_future_data", True)
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：千分之一印花税，买入时佣金万分之2.5，卖出时佣金万分之2.5， 每笔交易佣金最低扣5块钱
    # 基金类每笔交易时的手续费是：无印花税，买入时佣金万分之1，卖出时佣金万分之1， 每笔交易佣金最低扣5块钱
    #set_order_cost(OrderCost(close_tax=0.001, open_commission=0.00025, close_commission=0.00025, min_commission=5), type='stock')
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.0001, close_commission=0.0001, min_commission=5), type='fund')
    # 设置滑点,ETF单价较低滑点高了对影响较大
    set_slippage(PriceRelatedSlippage(0.001),type='fund')
    # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    # 日线策略，指定时间运行，如果后期要分钟级这里需要改成分钟级handle_data
    run_daily(my_trade, time='14:50', reference_security='000300.XSHG')
    
    g.stocks={
        '510500.XSHG',    # 中证500ETF
        '510300.XSHG',    # 沪深510300
        '510050.XSHG',    # 上证50
        '159949.XSHE',    # 创业板50
        '513100.XSHG',    # 纳指ETF
        '513500.XSHG',    # 标普500
        '159920.XSHE',    # 恒生ETF
        '513520.XSHG',    # 日经ETF
        '513030.XSHG',    # 德国30
        '162411.XSHE',    # 华宝油气
        '159985.XSHE'}    # 豆粕ETF 

    # 持仓状态
    g.position={'ETF_HOLD':'0', 'STATUS':0, 'HOLD_NUM':0}

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    print("持仓情况:{0}".format(g.position))
    
def after_code_changed(context):
    log.info('函数运行时间(after_code_changed)：'+str(context.current_dt.time()))
    # 更换后代码执行，尤其需要注意持仓情况
    print("持仓情况:{0}".format(g.position))


def my_trade(context):
    
    N=21     # N日前收盘价的涨幅

    # 该list用于存放计算出来的结果,并按动量排序
    SEC_LIST=[]
    SEC_LIST_DETAIL={}
    R_LIST=[]
    
    curr_data = get_current_data()
    
    for security in g.stocks:
        close_data1 = attribute_history(security, 30, unit='1d', fields=['close'])['close']    # 不包含当天数据
        #log.debug(close_data1)
        # 有些ETF成立时间较短，取不到数据则直接退出
        curr_price = curr_data[security].last_price    # 当前价
        #his_n_price = close_data1[-N]                  # 特定的一个历史价
        #his_n_price = (sum(close_data1[-(N-1):])+curr_price)/N      # N日均线
        his_n_price = sum(close_data1[-23:-20])/3      # 21日前3日均线
        
        if curr_price!=curr_price or his_n_price!=his_n_price or curr_price<0.01 or his_n_price<0.01:
            log.warning("未取到[%s]分钟级数据,直接退出！！！" % (curr_data[security].name))
            return
            #continue

        #R = (curr_price - his_n_price)*100/his_n_price         # 当前价较前N日前价格的涨幅
        # 用一天的价格进行判断，有时候一天涨跌太大，导致频繁换仓适得其反，用近3日均价跟21日前3日均价的涨幅来pa稍微平滑一点
        R = (close_data1[-2]+close_data1[-1]+curr_price-sum(close_data1[-23:-20]))*100/sum(close_data1[-23:-20])    
        
        base_price = close_data1[-N]                  # 特定的一个历史价，也也可以换为MA均线

        # 回测偶尔有遇到到R结果一致的情况，导致排序出错，如果有重复的加一个随机数
        if R in R_LIST:
            R = R + random.random()/1000
        R_LIST.append(R)
        SEC_LIST.append((R,security,curr_price,base_price))

    # 将ETF进行排序
    SEC_LIST.sort(reverse=True)
    ETF_No1 = SEC_LIST[0][1]
    
    if g.position['STATUS']==0:
        # 大于历史价才买进
        if SEC_LIST[0][2] > SEC_LIST[0][3]*1.001:
            log.info("目前空仓买入:%s" % ETF_No1)
            order_target_value(ETF_No1, context.portfolio.cash)
            g.position['STATUS'] = 1
            g.position['ETF_HOLD'] = ETF_No1
    elif g.position['STATUS']==1:
        if g.position['ETF_HOLD'] == ETF_No1:
            # 跌破历史价卖出
            if SEC_LIST[0][2] < SEC_LIST[0][3]*0.999:
                log.info("持仓%s排名第一，但小于历史价需要卖出" % g.position['ETF_HOLD'])
                order_target_value(g.position['ETF_HOLD'], 0)
                g.position['STATUS'] = 0
                g.position['ETF_HOLD'] = ' '
            else:
                log.info("持仓%s排名第一，继续持仓" % g.position['ETF_HOLD'])
        else:
            if SEC_LIST[0][2] > SEC_LIST[0][3]*1.001:
                order_target_value(g.position['ETF_HOLD'], 0)
                order_target_value(ETF_No1, context.portfolio.cash)
                g.position['ETF_HOLD'] = ETF_No1
    

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))

    log.info('一天结束')
    log.info('##############################################################\n\n')
    