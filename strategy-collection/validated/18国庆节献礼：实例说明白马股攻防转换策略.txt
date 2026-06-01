# 克隆自聚宽文章：https://www.joinquant.com/post/50043
# 标题：国庆节献礼：实例说明白马股攻防转换策略
# 作者：蚂蚁量化

# 克隆自聚宽文章：https://www.joinquant.com/post/41921
# 标题：大市值价值投资，从2005年至今超额稳定
# 作者：Ahfu

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
	log.info('初始函数开始运行且全局只运行一次')
	# 过滤掉order系列API产生的比error级别低的log
	log.set_level('order', 'error')
	

	# 股票池
	g.buy_stock_count = 5
	g.check_out_lists = []
	g.market_temperature = "warm"
	
	### 股票相关设定 ###
	set_order_cost(OrderCost(close_tax=0.001, open_commission=0.00012, close_commission=0.00012, min_commission=5),
				   type='stock')
	
	# 开盘前运行
	run_monthly(before_market_open, 1, time='5:00', reference_security='000300.XSHG')
	run_monthly(my_trade, 1, time='9:45', reference_security='000300.XSHG')
	# 收盘后运行
	run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')


## 开盘时运行函数
def my_trade(context):
	# 买卖
	adjust_position(context, g.check_out_lists)

## 收盘后运行函数
def after_market_close(context):
	log.info('#########################################################################################\n\n')


# 自定义下单
# 根据Joinquant文档，当前报单函数都是阻塞执行，报单函数（如order_target_value）返回即表示报单完成
# 报单成功返回报单（不代表一定会成交），否则返回None
def order_target_value_(security, value):
	if value == 0:
		log.debug("卖出 %s" % (get_name(security)))
	else:
		log.debug("买入 %s ，市值： %f" % (get_name(security), value))

	# 如果股票停牌，创建报单会失败，order_target_value 返回None
	# 如果股票涨跌停，创建报单会成功，order_target_value 返回Order，但是报单会取消
	# 部成部撤的报单，聚宽状态是已撤，此时成交量>0，可通过成交量判断是否有成交
	return order_target_value(security, value)


# 开仓，买入指定价值的证券
# 报单成功并成交（包括全部成交或部分成交，此时成交量大于0），返回True
# 报单失败或者报单成功但被取消（此时成交量等于0），返回False
def open_position(security, value):
	order = order_target_value_(security, value)
	if order != None and order.filled > 0:
		return True
	return False


# 平仓，卖出指定持仓
# 平仓成功并全部成交，返回True
# 报单失败或者报单成功但被取消（此时成交量等于0），或者报单非全部成交，返回False
def close_position(position):
	security = position.security
	order = order_target_value_(security, 0)  # 可能会因停牌失败
	if order != None:
		if order.status == OrderStatus.held and order.filled == order.amount:
			return True
	
	return False


# 交易
def adjust_position(context, buy_stocks):
	for stock in context.portfolio.positions:
		current_data = get_current_data()
		nosell_1 = context.portfolio.positions[stock].price >= current_data[stock].high_limit
		sell_2 = stock not in buy_stocks
		if sell_2 and not nosell_1:
			log.info("调出平仓：[%s]" % (stock))
			position = context.portfolio.positions[stock]
			close_position(position)
		else:
			log.info("已持仓，本次不买入：[%s]" % (stock))

	# 根据股票数量分仓
	# 此处只根据可用金额平均分配购买，不能保证每个仓位平均分配
	position_count = len(context.portfolio.positions)
	if g.buy_stock_count > position_count:
		value = context.portfolio.cash / (g.buy_stock_count - position_count)
		
		for stock in buy_stocks[:g.buy_stock_count]:
			if stock not in context.portfolio.positions:
				if open_position(stock, value):
					if len(context.portfolio.positions) >= g.buy_stock_count:
						break

# # 通过代码返回股票名称
def get_name(stk):
    return get_security_info(stk).display_name+':'+stk[:6]

#  tttttttttttt
def Market_temperature(context):
    
    index300 = attribute_history('000300.XSHG', 220, '1d', ('close'), df=False)['close']
    market_height = (mean(index300[-5:]) - min(index300)) / (max(index300) - min(index300))
    if market_height < 0.20:
        g.market_temperature = "cold"

    elif market_height > 0.90:
        g.market_temperature = "hot"

    elif max(index300[-60:]) / min(index300) > 1.20:
        g.market_temperature = "warm"

    
    if g.market_temperature == "cold":
        temp = 200
    elif g.market_temperature == "warm":
        temp = 300
    else:
        temp = 400
        
    if context.run_params.type != 'sim_trade':
        record(temp=temp)

## 开盘前运行函数
def before_market_open(context):
    Market_temperature(context)
    g.check_out_lists = []
    current_data = get_current_data()
    check_date = context.previous_date - datetime.timedelta(days=200)
    all_stocks = list(get_all_securities(date=check_date).index)
    all_stocks = get_index_stocks("000300.XSHG")
    # 过滤创业板、ST、停牌、当日涨停
    all_stocks = [stock for stock in all_stocks if not (
            (current_data[stock].day_open == current_data[stock].high_limit) or  # 涨停开盘
            (current_data[stock].day_open == current_data[stock].low_limit) or  # 跌停开盘
            current_data[stock].paused or  # 停牌
            current_data[stock].is_st or  # ST
            ('ST' in current_data[stock].name) or
            ('*' in current_data[stock].name) or
            ('退' in current_data[stock].name) or
            (stock.startswith('30')) or  # 创业
            (stock.startswith('68')) or  # 科创
            (stock.startswith('8')) or  # 北交
            (stock.startswith('4'))   # 北交
    )]
    if g.market_temperature == "cold":
        q = query(
            valuation.code, 
            ).filter(
            valuation.pb_ratio > 0,
            valuation.pb_ratio < 1,
            cash_flow.subtotal_operate_cash_inflow > 0,
            indicator.adjusted_profit > 0,
            cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit>2.0,
            indicator.inc_return > 1.5,
            indicator.inc_net_profit_year_on_year > -15,
        	valuation.code.in_(all_stocks)
        	).order_by(
        	(indicator.roa/valuation.pb_ratio).desc()
        ).limit(
        	g.buy_stock_count + 1
        )
    elif g.market_temperature == "warm":
        q = query(
            valuation.code, 
            ).filter(
            valuation.pb_ratio > 0,
            valuation.pb_ratio < 1,
            cash_flow.subtotal_operate_cash_inflow > 0,
            indicator.adjusted_profit > 0,
            cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit>1.0,
            indicator.inc_return > 2.0,
            indicator.inc_net_profit_year_on_year > 0,
        	valuation.code.in_(all_stocks)
        	).order_by(
        	(indicator.roa/valuation.pb_ratio).desc()
        ).limit(
        	g.buy_stock_count + 1
        )
    elif g.market_temperature == "hot":
        q = query(
            valuation.code, 
            ).filter(
 
            valuation.pb_ratio > 3,
            cash_flow.subtotal_operate_cash_inflow > 0,
            indicator.adjusted_profit > 0,
            cash_flow.subtotal_operate_cash_inflow/indicator.adjusted_profit>0.5,
            indicator.inc_return > 3.0,
            indicator.inc_net_profit_year_on_year > 20,
        	valuation.code.in_(all_stocks)
        	).order_by(
        	indicator.roa.desc()
        ).limit(
        	g.buy_stock_count + 1
        )
                
        
    check_out_lists = list(get_fundamentals(q).code)
    # 取需要的只数
    #check_out_lists = check_out_lists[:g.buy_stock_count]
    
    g.check_out_lists = check_out_lists
    log.info("今日股票池：%s" % g.check_out_lists)