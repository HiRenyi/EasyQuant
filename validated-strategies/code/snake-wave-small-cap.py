# 克隆自聚宽文章：https://www.joinquant.com/post/48284
# 标题：蛇皮走位小市值策略V1.0
# 作者：MarioC

# 克隆自聚宽文章：https://www.joinquant.com/post/45510
# 标题：5年15倍的收益，年化79.93%，可实盘，拿走不谢！
# 作者：langcheng999

from jqdata import *
import warnings
warnings.filterwarnings("ignore")

def initialize(context):
    # 设置基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 设置日志级别为error
    log.set_level('order', 'error')

    g.stock_num = 10  # 持股数量

    # 准备昨日涨停且正在持有的股票列表
    run_daily(prepare_high_limit_list, time='9:05', reference_security='000300.XSHG')
    # 每天调整昨日涨停股票
    run_daily(check_limit_up, time='14:00')
    run_daily(consistent, time='14:30')


# 1-3 整体调整持仓
def consistent(context):
    yesterday = context.previous_date
    now_time = context.current_dt
    stocks = get_index_stocks('399101.XSHE', now_time)
    q = query(valuation.code, valuation.circulating_market_cap, indicator.eps).filter(
        valuation.code.in_(stocks)).order_by(valuation.circulating_market_cap.asc())
    df = get_fundamentals(q)
    lst = list(df.code)[:20]
    h_ratio = get_price(lst, end_date = yesterday , frequency='1d', fields=['close'], count=2)['close']
    first_row = h_ratio.iloc[0]
    last_row = h_ratio.iloc[-1]
    change_BIG = (last_row - first_row) / first_row * 100
    A1=np.array(change_BIG)
    norm = np.linalg.norm(A1)
    normalized_array = A1 / norm
    variance = np.var(normalized_array)
    mean = np.mean(normalized_array)
    
    COST=[]
    current=[]
    for stock in context.portfolio.positions.keys():
        current.append(context.portfolio.positions[stock].price)
        COST.append(context.portfolio.positions[stock].avg_cost)
    paired_prices = zip(COST, current)
    # 计算涨跌幅
    change_list = [(current - cost) / cost for cost, current in paired_prices if current > cost]
    # 求和涨跌幅
    total_change = sum(change_list)
    print(total_change)

            
            
    if variance<0.02 and mean>0:
        target_list = choose_stocks(context)
        current_data = get_current_data()
        # Sell，仍在选出的股票池中，则不卖
        for s in context.portfolio.positions:
            if s in target_list or current_data[s].paused or current_data[s].last_price == current_data[s].high_limit:
                continue
            # log.info('Sell: %s %s' % (s, current_data[s].name))
            order_target(s, 0)
        # buy，根据资金买入相应的金额
        to_buy(context, target_list)
    
    
    if -0.1<total_change<0.4:
        pass
    else:
        print('等')
        hold_list = list(context.portfolio.positions)
        for s in hold_list:
            position = context.portfolio.positions[s]
            close_position(position)


# 准备昨日涨停且正在持有的股票列表
def prepare_high_limit_list(context):
    # 昨日涨停列表
    g.high_limit_list = []
    # 获取已持有列表
    hold_list = list(context.portfolio.positions)
    if hold_list:
        g.high_limit_list = get_price(
            hold_list, end_date=context.previous_date, frequency='daily',
            fields=['close', 'high_limit', 'paused'],
            count=1, panel=False).query('close == high_limit and paused == 0')['code'].tolist()


#  调整昨日涨停股票
def check_limit_up(context):
    sold_sth = False  # 是否因涨停检查卖出过股票
    current_data = get_current_data()
    for stock in g.high_limit_list:
        # 涨停的票，涨不动了就卖掉
        if current_data[stock].last_price < current_data[stock].high_limit:
            order_target(stock, 0)
            sold_sth = True
            # log.info("[%s]涨停打开，卖出" % stock)


# 每月选股
def choose_stocks(context):
    # 2-6 过滤次新股
    by_date = context.previous_date - datetime.timedelta(days=250)
    stocks = get_all_securities('stock', by_date).index.tolist()
    # 4 各种过滤
    stocks = filter_stock_basic(stocks)
    # 5 低价股
    stocks = filter_high_price_stock(stocks)
    # 3 基本面筛选，并根据小市值排序
    stocks = get_peg(stocks)
    # 截取不超过最大持仓数的股票量
    return stocks[:g.stock_num]


def filter_stock_basic(stock_list):
    curr_data = get_current_data()
    return [
        stock for stock in stock_list if not
        (
                stock.startswith(('68', '4', '8')) or  # '3', 创业，科创，北交所
                curr_data[stock].paused or
                curr_data[stock].is_st or  # ST
                (curr_data[stock].last_price >= curr_data[stock].high_limit * 0.97) or  # 涨停开盘, 其它时间用last_price
                (curr_data[stock].last_price <= curr_data[stock].low_limit * 1.04)  # 跌停开盘, 其它时间用last_price
        )]


# 2-4 过滤股价高于10元的股票
def filter_high_price_stock(stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list).iloc[0]
    return last_prices[last_prices < 10].index.tolist()




def to_buy(context, target_list):
    current_data = get_current_data()
    position_count = len(context.portfolio.positions)
    if position_count < g.stock_num:
        value = context.portfolio.available_cash / (g.stock_num - position_count)
        for s in target_list:
            if s not in context.portfolio.positions:
                # log.info('buy: %s %s' % (s, current_data[s].name))
                order_value(s, value)
                if len(context.portfolio.positions) == g.stock_num:
                    break


# 基本面筛选，并根据小市值排序
def get_peg(stocks):
    # 基本面选股
    stocks = get_fundamentals(
        query(
            valuation.code,
        ).filter(
            indicator.roe > 0.15,
            indicator.roa > 0.10,
            valuation.code.in_(stocks)
        ).order_by(
            valuation.market_cap.asc()  # 按市值升序排列
        )
    )['code'].tolist()

    return stocks
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)
    
# 3-3 交易模块-平仓
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)  # 可能会因停牌失败
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False