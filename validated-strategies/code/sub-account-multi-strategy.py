# 克隆自聚宽文章：https://www.joinquant.com/post/47344
# 标题：用子账户模拟多策略分仓
# 作者：赌神Buffett

'''
多策略分子账户并行

用到的策略：
wywy1995：机器学习多因子小市值
wywy1995、hayy：ETF核心资产轮动-添油加醋
Ahfu、伺底而动：大市值价值投资（改称PB策略）
开心果、十足的小市值迷、wzg3768、langcheng999：经典大妈买菜选股法高股息低价股

'''
# 导入函数库
from jqdata import *
from jqfactor import get_factor_values
import datetime


# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    set_slippage(PriceRelatedSlippage(0.01), type='stock')

    # 临时变量
    
    # 持久变量
    g.strategys = {}
    g.portfolio_value_proportion = [0.2,0.2,0.3,0.3]
    
    # 创建策略实例
    set_subportfolios([
        SubPortfolioConfig(context.portfolio.starting_cash*g.portfolio_value_proportion[0], 'stock'), 
        SubPortfolioConfig(context.portfolio.starting_cash*g.portfolio_value_proportion[1], 'stock'),
        SubPortfolioConfig(context.portfolio.starting_cash*g.portfolio_value_proportion[2], 'stock'),
        SubPortfolioConfig(context.portfolio.starting_cash*g.portfolio_value_proportion[3], 'stock'),
    ])
    
    params = {
        'max_hold_count': 1,    # 最大持股数
        'max_select_count': 1,  # 最大输出选股数
    }
    etf_strategy = ETF_Strategy(context, subportfolio_index=0, name='ETF轮动策略', params=params)
    g.strategys[etf_strategy.name] = etf_strategy
    
    params = {
        'max_hold_count': 1,        # 最大持股数
        'max_select_count': 3,      # 最大输出选股数
    }
    pb_strategy = PB_Strategy(context, subportfolio_index=1, name='PB策略', params=params)
    g.strategys[pb_strategy.name] = pb_strategy
    
    params = {
        'max_hold_count': 3,        # 最大持股数
        'max_select_count': 5,      # 最大输出选股数
        'use_empty_month': True,    # 是否在指定月份空仓
        'empty_month': [4],         # 指定空仓的月份列表
        'use_stoplost': True,       # 是否使用止损
    }
    xsz_strategy = XSZ_Strategy(context, subportfolio_index=2, name='小市值策略', params=params)
    g.strategys[xsz_strategy.name] = xsz_strategy

    params = {
        'max_hold_count': 1,        # 最大持股数
        'max_select_count': 3,      # 最大输出选股数
        # 'use_empty_month': True,    # 是否在指定月份空仓
        # 'empty_month': [4],         # 指定空仓的月份列表
        'use_stoplost': True,       # 是否使用止损
    }
    dama_strategy = DaMa_Strategy(context, subportfolio_index=3, name='菜场大妈策略', params=params)
    g.strategys[dama_strategy.name] = dama_strategy

    # 执行计划
    if g.portfolio_value_proportion[0] > 0:
        run_daily(etf_select, '7:40') 
        run_daily(etf_adjust, '10:00')
    if g.portfolio_value_proportion[1] > 0:
        run_daily(pb_day_prepare, time='7:30')
        run_monthly(pb_select, 1, time='7:40')
        run_daily(pb_open_market, time='9:30')
        run_monthly(pb_adjust, 1, time='9:35')
        run_daily(pb_sell_when_highlimit_open, time='14:00')
        run_daily(pb_sell_when_highlimit_open, time='14:50')
    if g.portfolio_value_proportion[2] > 0:
        run_daily(xsz_day_prepare, time='7:30')
        run_weekly(xsz_select, 1, time='7:40')
        run_daily(xsz_open_market, time='9:30')
        run_weekly(xsz_adjust, 1, time='9:35')
        run_daily(xsz_sell_when_highlimit_open, time='14:00')
        run_daily(xsz_sell_when_highlimit_open, time='14:50')
    if g.portfolio_value_proportion[3] > 0:
        run_daily(dama_day_prepare, time='7:30')
        run_monthly(dama_select, 15, time='7:40')
        run_daily(dama_open_market, time='9:30')
        run_monthly(dama_adjust, 15, time='10:30')
        run_daily(dama_sell_when_highlimit_open, time='14:00')
        run_daily(dama_sell_when_highlimit_open, time='14:50')
        
    # run_daily(print_trade_info, time='15:01')


def etf_select(context):
    g.strategys['ETF轮动策略'].select(context)

def etf_adjust(context):
    g.strategys['ETF轮动策略'].adjust(context)


def pb_day_prepare(context):
    g.strategys['PB策略'].day_prepare(context)

def pb_select(context):
    g.strategys['PB策略'].select(context)
        
def pb_adjust(context):
    g.strategys['PB策略'].adjust(context)

def pb_open_market(context):
    g.strategys['PB策略'].close_for_stoplost(context)

def pb_sell_when_highlimit_open(context):
    g.strategys['PB策略'].sell_when_highlimit_open(context)


def xsz_day_prepare(context):
    g.strategys['小市值策略'].day_prepare(context)

def xsz_select(context):
    g.strategys['小市值策略'].select(context)

def xsz_adjust(context):
    g.strategys['小市值策略'].adjust(context)

def xsz_open_market(context):
    g.strategys['小市值策略'].close_for_empty_month(context)
    g.strategys['小市值策略'].close_for_stoplost(context)

def xsz_sell_when_highlimit_open(context):
    g.strategys['小市值策略'].sell_when_highlimit_open(context)


def dama_day_prepare(context):
    g.strategys['菜场大妈策略'].day_prepare(context)

def dama_select(context):
    g.strategys['菜场大妈策略'].select(context)

def dama_adjust(context):
    g.strategys['菜场大妈策略'].adjust(context)

def dama_open_market(context):
    g.strategys['菜场大妈策略'].close_for_empty_month(context)
    g.strategys['菜场大妈策略'].close_for_stoplost(context)

def dama_sell_when_highlimit_open(context):
    g.strategys['菜场大妈策略'].sell_when_highlimit_open(context)
    
    
# 打印交易记录
def print_trade_info(context):
    orders = get_orders()
    for _order in orders.values():
        print('成交记录：'+str(_order))
        

# 策略基类
# 同一只股票只买入1次，卖出时全部卖出
class Strategy:
    def __init__(self, context, subportfolio_index, name, params):
        self.subportfolio_index = subportfolio_index
        # self.subportfolio = context.subportfolios[subportfolio_index]
        self.name = name
        self.params = params
        self.max_hold_count = self.params['max_hold_count'] if 'max_hold_count' in self.params else 1                       # 最大持股数
        self.max_select_count = self.params['max_select_count'] if 'max_select_count' in self.params else 5                 # 最大输出选股数
        self.hold_limit_days = self.params['hold_limit_days'] if 'hold_limit_days' in self.params else 20                   # 计算最近持有列表的天数
        self.use_empty_month = self.params['use_empty_month'] if 'use_empty_month' in self.params else False                # 是否有空仓期
        self.empty_month = self.params['empty_month'] if 'empty_month' in self.params else []                               # 空仓月份
        self.use_stoplost = self.params['use_stoplost'] if 'use_stoplost' in self.params else False                         # 是否使用止损
        self.stoplost_silent_days = self.params['stoplost_silent_days'] if 'stoplost_silent_days' in self.params else 20    # 止损后不交易的天数
        self.stoplost_level = self.params['stoplost_level'] if 'stoplost_level' in self.params else 0.2                     # 止损的下跌幅度（按买入价）

        self.select_list = []
        self.hold_list = []                 # 昨收持仓
        self.history_hold_list = []         # 最近持有列表
        self.not_buy_again_list = []        # 最近持有不再购买列表
        self.yestoday_high_limit_list = []  # 昨日涨停列表
        self.stoplost_date = None           # 止损日期，为None是表示未进入止损


    def day_prepare(self, context):
        subportfolio = context.subportfolios[self.subportfolio_index]
        
        # 获取昨日持股列表
        self.hold_list = list(subportfolio.long_positions)
        
        # 获取最近一段时间持有过的股票列表
        self.history_hold_list.append(self.hold_list)
        if len(self.history_hold_list) >= self.hold_limit_days:
            self.history_hold_list = self.history_hold_list[-self.hold_limit_days:]
        temp_set = set()
        for lists in self.history_hold_list:
            for stock in lists:
                temp_set.add(stock)
        self.not_buy_again_list = list(temp_set)
        
        # 获取昨日持股涨停列表
        if self.hold_list != []:
            df = get_price(self.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit'], count=1, panel=False, fill_paused=False)
            df = df[df['close'] == df['high_limit']]
            self.yestoday_high_limit_list = list(df.code)
        else:
            self.yestoday_high_limit_list = []
        
        # 检查空仓期
        self.check_empty_month(context)
        # 检查止损
        self.check_stoplost(context)
        
    
    # 基础股票池
    def stockpool(self, context, pool_id=1):
        lists = list(get_all_securities(types=['stock'], date=context.previous_date).index)
        if pool_id ==0:
            pass
        elif pool_id == 1:
            lists = self.filter_kcbj_stock(lists)
            lists = self.filter_st_stock(lists)
            lists = self.filter_paused_stock(lists)
            lists = self.filter_highlimit_stock(context, lists)
            lists = self.filter_lowlimit_stock(context, lists)
            
        return lists
        
    
    # 选股
    def select(self, context):
        # 空仓期控制
        if self.use_empty_month and context.current_dt.month in (self.empty_month):
            return
        # 止损期控制
        if self.stoplost_date is not None:
            return
        select.select_list = []
    
    
    # 打印交易计划
    def print_trade_plan(self, context, select_list):
        subportfolio = context.subportfolios[self.subportfolio_index]
        current_data = get_current_data()   # 取股票名称
    
        content = context.current_dt.date().strftime("%Y-%m-%d") + ' ' + self.name + " 交易计划：" + "\n"

        for stock in subportfolio.long_positions:
            if stock not in select_list[:self.max_hold_count]:
                content = content + stock + ' ' + current_data[stock].name + ' 卖出\n'

        for stock in select_list:
            if stock not in subportfolio.long_positions and stock in select_list[:self.max_hold_count]:
                content = content + stock + ' ' + current_data[stock].name + ' 买入\n'
            elif stock in subportfolio.long_positions and stock in select_list[:self.max_hold_count]:
                content = content + stock + ' ' + current_data[stock].name + ' 继续持有\n'
            else:
                content = content + stock + ' ' + current_data[stock].name + '\n'

        if ('买' in content) or ('卖' in content):
            print(content)


    # 调仓
    def adjust(self, context):
        # 空仓期控制
        if self.use_empty_month and context.current_dt.month in (self.empty_month):
            return
        # 止损期控制
        if self.stoplost_date is not None:
            return
        
        # 先卖后买
        hold_list = list(context.subportfolios[self.subportfolio_index].long_positions)
        sell_stocks = []
        for stock in hold_list:
            if stock not in self.select_list[:self.max_hold_count]:
                sell_stocks.append(stock)
        self.sell(context, sell_stocks)
        self.buy(context, self.select_list)


    # 涨停打开卖出
    def sell_when_highlimit_open(self, context):
        if self.yestoday_high_limit_list != []:
            for stock in self.yestoday_high_limit_list:
                if stock in context.subportfolios[self.subportfolio_index].long_positions:
                    current_data = get_price(stock, end_date=context.current_dt, frequency='1m', fields=['close','high_limit'], 
                        skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
                    if current_data.iloc[0,0] < current_data.iloc[0,1]:
                        self.sell(context, [stock])
                        content = context.current_dt.date().strftime("%Y-%m-%d") + ' ' + self.name + ': {}涨停打开，卖出'.format(stock) + "\n"
                        print(content)


    
    # 空仓期检查
    def check_empty_month(self, context):
        subportfolio = context.subportfolios[self.subportfolio_index]
        if self.use_empty_month and context.current_dt.month in (self.empty_month) and len(subportfolio.long_positions) > 0:
            content = context.current_dt.date().strftime("%Y-%m-%d") + self.name + ': 进入空仓期' + "\n"
            for stock in subportfolio.long_positions:
                content = content + stock + "\n"
            print(content)


    # 进入空仓期清仓
    def close_for_empty_month(self, context):
        subportfolio = context.subportfolios[self.subportfolio_index]
        if self.use_empty_month and context.current_dt.month in (self.empty_month) and len(subportfolio.long_positions) > 0:
            self.sell(context, list(subportfolio.long_positions))


    # 止损检查
    def check_stoplost(self, context):
        subportfolio = context.subportfolios[self.subportfolio_index]
        if self.use_stoplost:
            if self.stoplost_date is None:
                last_prices = history(1, unit='1m', field='close', security_list=subportfolio.long_positions)
                for stock in subportfolio.long_positions:
                    position = subportfolio.long_positions[stock]
                    if (position.avg_cost-last_prices[stock][-1])/position.avg_cost > self.stoplost_level:
                        self.stoplost_date = context.current_dt.date()
                        print(self.name + ': ' + '开始止损')
                        content = context.current_dt.date().strftime("%Y-%m-%d") + ' ' + self.name + ': 止损' + "\n"
                        for stock in subportfolio.long_positions:
                            content = content + stock + "\n"
                        print(content)
                        break
            else:   # 已经在清仓静默期
                if (context.current_dt + datetime.timedelta(days=-self.stoplost_silent_days)).date() >= self.stoplost_date:
                    self.stoplost_date = None
                    print(self.name + ': ' + '退出止损')
    
    
    # 止损时清仓
    def close_for_stoplost(self, context):
        subportfolio = context.subportfolios[self.subportfolio_index]
        if self.use_stoplost and self.stoplost_date is not None and len(subportfolio.long_positions) > 0:
            self.sell(context, list(subportfolio.long_positions))
    

    # 买入多只股票
    def buy(self, context, buy_stocks):
        subportfolio = context.subportfolios[self.subportfolio_index]
        buy_count = self.max_hold_count - len(subportfolio.long_positions)
        if buy_count > 0:
            value = subportfolio.available_cash / buy_count
            index = 0
            for stock in buy_stocks:
                if stock in subportfolio.long_positions:
                    continue
                self.__open_position(stock, value)
                index = index + 1
                if index >= buy_count:
                    break
        
    
    # 卖出多只股票
    def sell(self, context, sell_stocks):
        subportfolio = context.subportfolios[self.subportfolio_index]
        for stock in sell_stocks:
            if stock in subportfolio.long_positions:
                self.__close_position(stock)
            

    # 开仓单只
    def __open_position(self, security, value):
        order = order_target_value(security, value, pindex=self.subportfolio_index)
        if order != None and order.filled > 0:
            return True
        return False
    
    
    # 清仓单只
    def __close_position(self, security):
        order = order_target_value(security, 0, pindex=self.subportfolio_index)
        if order != None and order.status == OrderStatus.held and order.filled == order.amount:
            return True
        return False


    # 过滤科创北交
    def filter_kcbj_stock(self, stock_list):
        for stock in stock_list[:]:
            if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
                stock_list.remove(stock)
        return stock_list
    

    # 过滤停牌股票
    def filter_paused_stock(self, stock_list):
        current_data = get_current_data()
        return [stock for stock in stock_list if not current_data[stock].paused]
    
    
    # 过滤ST及其他具有退市标签的股票
    def filter_st_stock(self, stock_list):
        current_data = get_current_data()
        return [stock for stock in stock_list
                if not current_data[stock].is_st
                and 'ST' not in current_data[stock].name
                and '*' not in current_data[stock].name
                and '退' not in current_data[stock].name]
    

    # 过滤涨停的股票
    def filter_highlimit_stock(self, context, stock_list):
        subportfolio = context.subportfolios[self.subportfolio_index]
        last_prices = history(1, unit='1m', field='close', security_list=stock_list)
        current_data = get_current_data()
        
        # 已存在于持仓的股票即使涨停也不过滤，避免此股票再次可买，但因被过滤而导致选择别的股票
        return [stock for stock in stock_list if stock in subportfolio.long_positions
            or  last_prices[stock][-1] < current_data[stock].high_limit]
    
    
    # 过滤跌停的股票
    def filter_lowlimit_stock(self, context, stock_list):
        subportfolio = context.subportfolios[self.subportfolio_index]
        last_prices = history(1, unit='1m', field='close', security_list=stock_list)
        current_data = get_current_data()
        
        return [stock for stock in stock_list if stock in subportfolio.long_positions
                or last_prices[stock][-1] > current_data[stock].low_limit]
    
    
    # 过滤次新股
    def filter_new_stock(self, context, stock_list, days):
        return [stock for stock in stock_list if not context.previous_date - get_security_info(stock).start_date < datetime.timedelta(days=days)]


    # 过滤大幅解禁
    def filter_locked_shares(self, context, stock_list, days):
        df = get_locked_shares(stock_list=stock_list, start_date=context.previous_date.strftime('%Y-%m-%d'), forward_count=days)
        df = df[df['rate1']>0.2]    # 解禁数量占总股本的百分比
        filterlist = list(df['code'])
        return [stock for stock in stock_list if stock not in filterlist]


# ETF轮动策略
class ETF_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name, params):
        super().__init__(context, subportfolio_index, name, params)
        self.etf_pool = [
            '510180.XSHG', #上证180
            '159915.XSHE', #创业板100（成长股，科技股，题材性，中小盘）
            '513100.XSHG', #纳指100（海外资产）
            '518880.XSHG', #黄金ETF（大宗商品）
        ]
        self.m_days = 25 #动量参考天数
    
    
    def select(self, context):
        self.select_list = self.__get_rank(context)[:self.max_select_count]
        self.print_trade_plan(context, self.select_list)

    
    def __get_rank(self, context):
        etf_pool = self.etf_pool
        score_list = []
        for etf in etf_pool:
            #每只股票计算分数流程
            df = attribute_history(etf, self.m_days, '1d', ['close'])
            y = df['log'] = np.log(df.close)
            x = df['num'] = np.arange(df.log.size)
            slope, intercept = np.polyfit(x, y, 1)
            annualized_returns = math.pow(math.exp(slope), 250) - 1
            r_squared = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
            score = annualized_returns * r_squared   # 运用线性回归算出来的年度收益率×R方
            
            # 加入反转
            df2 = attribute_history(etf, self.m_days*8, '1d', ['close'])
            y2= df2['log'] = np.log(df2.close)
            x2 = df2['num'] = np.arange(df2.log.size)
            slope2, intercept2 = np.polyfit(x2, y2, 1)
            annualized_returns2 = math.pow(math.exp(slope2), 250) - 1
            r_squared2 = 1 - (sum((y2 - (slope2 * x2 + intercept2))**2) / ((len(y2) - 1) * np.var(y2, ddof=1)))
            
            score= score - annualized_returns2 * r_squared2 / 6
            
            score_list.append(score)
            
        df = pd.DataFrame(index=etf_pool, data={'score':score_list})
        rank_df = df.sort_values(by='score', ascending=False) # 从大到小 
        
        c = max(list(rank_df.score)) - min(list(rank_df.score))
        if c < 15 and c > 0.1 :
            target_list = list(rank_df.index)[0:self.max_hold_count]
        else:
            target_list = []
        
        # rsrs择时
        real_target_list = []
        for etf in target_list:
            hl = attribute_history(etf, 18, '1d', ['high','low'])
            if np.polyfit(hl.low,hl.high,1)[0] > self.__count_beta(context, etf):
                real_target_list.append(etf)

        return real_target_list


    def __count_beta(self, context, etf):
        etf_data = attribute_history(etf, 250, '1d', fields=['high','low'])
        betaList = []
        try:
            for i in range(0,len(etf_data)-21):
                df = etf_data.iloc[i:i+20,:]
                betaList.append(np.polyfit(df.low,df.high,1)[0])
            return (mean(betaList)-2*std(betaList))
        except:
            return 0


# PB策略
class PB_Strategy(Strategy):
    def select(self, context):
        self.select_list = self.__get_rank(context)[:self.max_select_count]
        self.print_trade_plan(context, self.select_list)
    
    
    def __get_rank(self, context):
        lists = self.stockpool(context)
    
        # 基本股选股
        q = query(
                valuation.code, valuation.market_cap, valuation.pe_ratio, income.total_operating_revenue
            ).filter(
                valuation.pb_ratio < 0.98,
                # valuation.pb_ratio > 0.5,
                cash_flow.subtotal_operate_cash_inflow > 1e6,
                indicator.adjusted_profit > 1e6,
                indicator.roa > 0.15,
                indicator.inc_operation_profit_year_on_year > 0,
            	valuation.code.in_(lists)
        	).order_by(
        	    indicator.roa.desc()
            ).limit(
            	self.max_select_count * 3
            )
        lists = list(get_fundamentals(q).code)
        return lists


# 小市值策略
class XSZ_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name, params):
        super().__init__(context, subportfolio_index, name, params)
        self.new_days = 400 # 已上市天数
        self.factor_list = [
            (#ARBR-SGAI-NPtTORttm-RPps
                [
                    'ARBR', #情绪类因子 ARBR
                    'SGAI', #质量类因子 销售管理费用指数
                    'net_profit_to_total_operate_revenue_ttm', #质量类因子 净利润与营业总收入之比
                    'retained_profit_per_share' #每股指标因子 每股未分配利润
                ],
                [
                    -2.3425,
                    -694.7936,
                    -170.0463,
                    -1362.5762
                ]
            ),
            (#P1Y-TPtCR-VOL120
                [
                    'Price1Y', #动量类因子 当前股价除以过去一年股价均值再减1
                    'total_profit_to_cost_ratio', #质量类因子 成本费用利润率
                    'VOL120' #情绪类因子 120日平均换手率
                ],
                [
                    -0.0647128120839873,
                    -0.006385116279168804,
                    -0.0029867925845833217
                ]
            ),
            (#DtA-OCtORR-DAVOL20-PNF-SG
                [
                    'debt_to_assets', #风格因子 资产负债率
                    'operating_cost_to_operating_revenue_ratio', #质量类因子 销售成本率
                    'DAVOL20', #情绪类因子 20日平均换手率与120日平均换手率之比
                    'price_no_fq', #技术指标因子 不复权价格因子
                    'sales_growth' #风格因子 5年营业收入增长率
                ],
                [
                    0.04477354820057883,
                    0.021636407482421707,
                    -0.01864268317469762,
                    -0.0004678118383947827,
                    0.02884867440332058
                ]
            ),
        ]
        self.stock_factor_dict = {}


    def select(self, context):
        # 空仓期控制
        if self.use_empty_month and context.current_dt.month in (self.empty_month):
            return
        # 止损期控制
        if self.stoplost_date is not None:
            return
        self.select_list = self.__get_rank(context)[:self.max_select_count]
        self.print_trade_plan(context, self.select_list)
    
    
    def __get_rank(self, context):
        initial_list = self.stockpool(context)
        initial_list = self.filter_new_stock(context, initial_list, self.new_days)
        initial_list = self.filter_locked_shares(context, initial_list, 120)    # 过滤即将大幅解禁
        
        final_list = []
        #MS
        for factor_list, coef_list in self.factor_list:
            factor_values = get_factor_values(initial_list, factor_list, end_date=context.previous_date, count=1)
            df = pd.DataFrame(index=initial_list, columns=factor_values.keys())
            for i in range(len(factor_list)):
                df[factor_list[i]] = list(factor_values[factor_list[i]].T.iloc[:,0])
            df = df.dropna()
            
            df['total_score'] = 0
            for i in range(len(factor_list)):
                df['total_score'] += coef_list[i]*df[factor_list[i]]
            df = df.sort_values(by=['total_score'], ascending=False) #分数越高即预测未来收益越高，排序默认降序
            complex_factor_list = list(df.index)[:int(0.1*len(list(df.index)))]
            q = query(
                    valuation.code,valuation.circulating_market_cap,indicator.eps
                ).filter(
                    valuation.code.in_(complex_factor_list)
                )
                # .order_by(
                #     valuation.circulating_market_cap.asc()
                # )
            df = get_fundamentals(q)
            df = df[df['eps'] > 0]
            lst  = list(df.code)
            final_list = list(set(final_list + lst))
                
        # 再做一次市值过滤
        q = query(valuation.code). \
            filter(valuation.code.in_(final_list)). \
            order_by(valuation.circulating_market_cap.asc())
        df = get_fundamentals(q)
        final_list = list(df.code)
        final_list = final_list[:self.max_select_count]
        return final_list


# 市场大妈策略
class DaMa_Strategy(Strategy):
    def __init__(self, context, subportfolio_index, name, params):
        super().__init__(context, subportfolio_index, name, params)
        

    def select(self, context):
        # 空仓期控制
        if self.use_empty_month and context.current_dt.month in (self.empty_month):
            return
        # 止损期控制
        if self.stoplost_date is not None:
            return
        self.select_list = self.__get_rank(context)[:self.max_select_count]
        self.print_trade_plan(context, self.select_list)
    
    
    def __get_rank(self, context):
        initial_list = self.stockpool(context)
        #高股息(全市场最大25%)
        stocks = self.get_dividend_ratio_filter_list(context, initial_list, False, 0, 0.26)
        df = get_fundamentals(query(valuation.code).filter(valuation.code.in_(stocks)).order_by(valuation.market_cap.asc()))
        stocks = list(df.code)
        stocks = self.filter_highprice_stock(context, stocks)
        return stocks
        

    def filter_highprice_stock(self, context, stock_list):
    	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    	return [stock for stock in stock_list if stock in context.subportfolios[self.subportfolio_index].long_positions
    			or last_prices[stock][-1] < 9]
			
			
    # 根据最近一年分红除以当前总市值计算股息率并筛选    
    def get_dividend_ratio_filter_list(self, context, stock_list, sort, p1, p2):
        time1 = context.previous_date
        time0 = time1 - datetime.timedelta(days=365)
        #获取分红数据，由于finance.run_query最多返回4000行，以防未来数据超限，最好把stock_list拆分后查询再组合
        interval = 1000 #某只股票可能一年内多次分红，导致其所占行数大于1，所以interval不要取满4000
        list_len = len(stock_list)
        #截取不超过interval的列表并查询
        q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
        ).filter(
            finance.STK_XR_XD.a_registration_date >= time0,
            finance.STK_XR_XD.a_registration_date <= time1,
            finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
        df = finance.run_query(q)
        #对interval的部分分别查询并拼接
        if list_len > interval:
            df_num = list_len // interval
            for i in range(df_num):
                q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
                ).filter(
                    finance.STK_XR_XD.a_registration_date >= time0,
                    finance.STK_XR_XD.a_registration_date <= time1,
                    finance.STK_XR_XD.code.in_(stock_list[interval*(i+1):min(list_len,interval*(i+2))]))
                temp_df = finance.run_query(q)
                df = df.append(temp_df)
        dividend = df.fillna(0)
        dividend = dividend.set_index('code')
        dividend = dividend.groupby('code').sum()
        temp_list = list(dividend.index) #query查询不到无分红信息的股票，所以temp_list长度会小于stock_list
        #获取市值相关数据
        q = query(valuation.code,valuation.market_cap).filter(valuation.code.in_(temp_list))
        cap = get_fundamentals(q, date=time1)
        cap = cap.set_index('code')
        #计算股息率
        DR = pd.concat([dividend, cap] ,axis=1, sort=False)
        DR['dividend_ratio'] = (DR['bonus_amount_rmb']/10000) / DR['market_cap']
        #排序并筛选
        DR = DR.sort_values(by=['dividend_ratio'], ascending=sort)
        final_list = list(DR.index)[int(p1*len(DR)):int(p2*len(DR))]
        return final_list