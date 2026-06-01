# 克隆自聚宽文章：https://www.joinquant.com/post/46876
# 标题：大市值价值投资优化一波
# 作者：七八十

# 克隆自聚宽文章：https://www.joinquant.com/post/41921
# 标题：大市值价值投资，从2005年至今超额稳定
# 作者：Ahfu

"""
一直担心天天想着年化N倍的圣杯策略，到最后发现都是白折腾，徒耗光阴，蓦然回首还是价值投资才是最终的归宿？毕竟这条路上有无数成功的先例。

思路：
1、选上市200天以上主板成熟个股；
2、价格低于价值（pb< 1）；
3、公司真的在不断赚钱，赚真钱，主要用到：
（1）经营现金流：这个比利润真实，不像利润容易作假；
（2）扣非净利润：别靠做账做出假利润；
（3）总资产收益率：别靠负债做高ROE；
（4）净利润同比增长：说明经营良好；

再加上排序指标，取前5支，每月调仓。

随着股市波动，在大牛市顶端会自动空仓留住利润，因为那个位置选不出有价值的票了。
"""

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
	# 设定沪深300作为基准
	set_benchmark('000300.XSHG')
	# 开启动态复权模式(真实价格)
	set_option('use_real_price', True)
	#防止未来函数
	set_option("avoid_future_data", True)
	
	# 输出内容到日志 log.info()
	# 过滤掉order系列API产生的比error级别低的log
	log.set_level('order', 'error')
	
	### 股票相关设定 ###
	set_order_cost(OrderCost(close_tax=0.001, open_commission=0.00012, close_commission=0.00012, min_commission=5),
				   type='stock')
	set_slippage(FixedSlippage(0.001))
	
	# 股票池
	g.buy_stock_count = 1
	g.check_out_lists = []
	
	# 国债 ETF
	g.etf = "511010.XSHG"
	
	# 昨日涨停
	g.yesterday_HL_list = []
	
	# 开盘前运行
	run_daily(before_market_open, time='9:00')
	run_monthly(check_stocks, 1, time='9:05')
	run_monthly(my_trade, 1, time='9:30')
# 	run_weekly(check_stocks, 1, time='9:05')
# 	run_weekly(my_trade, 1, time='9:30')
	run_daily(check_limit_up, time="14:00")
	run_daily(check_limit_up, time="14:50")

## 开盘前运行函数
def before_market_open(context):
    # 获取股票已持有列表
    hold_list = [stock for stock in context.portfolio.positions if stock != g.etf]

    # 获取昨日涨停列表
    g.yesterday_HL_list.clear()
    if len(hold_list) != 0:
        df = get_price(
            hold_list,
            end_date=context.previous_date,
            frequency="daily",
            fields=["close", "high_limit"],
            count=1,
            panel=False,
            fill_paused=False,
        )
        df = df[df["close"] == df["high_limit"]]
        g.yesterday_HL_list = list(df.code)
    
## 开盘时运行函数
def my_trade(context):
    # 过滤涨跌停
    stocks = filter_limitup_stock(context, g.check_out_lists)
    stocks = filter_limitdown_stock(context, stocks)
    
    # 卖出
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        if stock in stocks:
            log.info("已持仓，本次不买入：[%s]" % (stock))
            continue
        
        if stock in g.yesterday_HL_list:
            continue
            
        if current_data[stock].last_price < current_data[stock].high_limit:
            log.info("调出平仓：[%s]" % (stock))
            order_target(stock, 0)
        else:
            g.yesterday_HL_list.append(stock)
            
    # 分仓买入
    position_count = len(context.portfolio.positions)
    if g.buy_stock_count > position_count:
        value = context.portfolio.cash / (g.buy_stock_count - position_count)
        
        for stock in stocks:
            if stock in context.portfolio.positions:
                continue
                
            if order_target_value(stock, value):
                if len(context.portfolio.positions) == g.buy_stock_count:
                    break

def check_limit_up(context):
    current_data = get_current_data()

    # 对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
    for stock in g.yesterday_HL_list:
        if current_data[stock].last_price < current_data[stock].high_limit:
            log.info("[%s]涨停打开，卖出" % (stock))
            order_target(stock, 0)
        else:
            log.info("[%s]涨停，继续持有" % (stock))

    # 可用资金买入 etf
    order_value(g.etf, context.portfolio.available_cash)
    
    # notify_adjust()
    
def check_stocks(context):
    current_data = get_current_data()
    check_date = context.previous_date - datetime.timedelta(days=200)
    all_stocks = list(get_all_securities(date=check_date).index)
    
    # 过滤创业板、ST、停牌、当日涨停
    all_stocks = [stock for stock in all_stocks if not (
            current_data[stock].paused or  # 停牌
            current_data[stock].is_st or  # ST
            # ('ST' in current_data[stock].name) or
            # ('*' in current_data[stock].name) or
            ('退' in current_data[stock].name) or
            # (stock.startswith('30')) or  # 创业
            (stock.startswith('68')) or  # 科创
            (stock.startswith('8')) or  # 北交
            (stock.startswith('4'))   # 北交
    )]
    
    # 基本股选股
    q = query(
        valuation.code, valuation.market_cap, valuation.pe_ratio, income.total_operating_revenue
        ).filter(
        valuation.pb_ratio < 1,
        # valuation.pb_ratio > 0.5,
        cash_flow.subtotal_operate_cash_inflow > 1e6,
        indicator.adjusted_profit > 1e6,
        indicator.roa > 0.15,
        indicator.inc_net_profit_year_on_year > 0,
    	valuation.code.in_(all_stocks)
    	).order_by(
    	indicator.roa.desc()
    ).limit(
    	g.buy_stock_count * 3
    )
    check_out_lists = list(get_fundamentals(q).code)
    
    # 取需要的数量
    g.check_out_lists = check_out_lists[:g.buy_stock_count]
    
    log.info("今日股票池：%s" % g.check_out_lists)
    
def filter_limitup_stock(context, stock_list):
    current_data = get_current_data()
    return [
        stock
        for stock in stock_list
        if stock in context.portfolio.positions
        or current_data[stock].last_price < current_data[stock].high_limit
    ]


def filter_limitdown_stock(context, stock_list):
    current_data = get_current_data()
    return [
        stock
        for stock in stock_list
        if stock in context.portfolio.positions
        or current_data[stock].last_price > current_data[stock].low_limit
    ]
    