# 克隆自聚宽文章：https://www.joinquant.com/post/47978
# 标题：wywy1995 首板低开策略代码优化，提快速度
# 作者：养家大哥

# 克隆自聚宽文章：https://www.joinquant.com/post/44901
# 标题：首板低开策略
# 作者：wywy1995

from jqlib.technical_analysis import *
from jqfactor import *
from jqdata import *
import datetime as dt
import pandas as pd



def initialize(context):
    # 系统设置
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.set_level('system', 'error')
    #enable_profile()
    set_slippage(PriceRelatedSlippage(0.003),type='stock')
    # 每日运行
    run_daily(prepare_stock, '09:15')
    run_daily(buy, '9:26') #9:25分知道开盘价后可以提前下单
    run_daily(sell1, '11:28')
    run_daily(sell2, '14:50')
    g.stock_list = []

# 选股
def prepare_stock(context):
        # 基础信息
    date = transform_date(context.previous_date, 'str')
    current_data = get_current_data()
    
    # 昨日涨停列表
    initial_list = prepare_stock_list(date)
    hl_list = get_hl_stock(initial_list, date)
    g.stock_list = []
    if len(hl_list) != 0:    
        # 获取非连板涨停的股票
        ccd = get_continue_count_df(hl_list, date, 10)
        lb_list = list(ccd.index)
        stock_list = [s for s in hl_list if s not in lb_list]
        
        # 计算相对位置
        rpd = get_relative_position_df(stock_list, date, 60)
        rpd = rpd[rpd['rp'] <= 0.5]
        #if(len(list(rpd.index))>0):
        #    g.stock_list = filter_low_limits(list(rpd.index), date, 20)
        g.stock_list = list(rpd.index)
        #g.stock_list = get_hl_stock_at_time(stock_list, date, '14:55:00')
        buy_str = ''
        for stock in g.stock_list:
            buy_str += "%s%s;"%(stock, get_security_info(stock).display_name)
        send_message('可能股票：%s '%(buy_str))
        log.info('可能股票：%s '%(buy_str))

# 选股
def buy(context):
    
    # 基础信息
    date = transform_date(context.previous_date, 'str')
    current_data = get_current_data()
    stock_list = g.stock_list
    if len(stock_list) != 0:    
        # 低开
        df =  get_price(stock_list, end_date=date, frequency='daily', fields=['close'], count=1, panel=False, fill_paused=False, skip_paused=True).set_index('code') if len(stock_list) != 0 else pd.DataFrame()
        df['open_pct'] = [current_data[s].day_open/df.loc[s, 'close'] for s in stock_list]
        #df['open_pct2'] = [(df.loc[s, 'close']-current_data[s].day_open)/df.loc[s, 'close'] for s in stock_list]
        #print(rpd)
        #print(df)
        df = df[(0.96 <= df['open_pct']) & (df['open_pct'] <= 0.97)] #低开越多风险越大，选择3个多点即可
        #df = df[(0.03 <= df['open_pct2']) & (df['open_pct2'] <= 0.04)] #低开越多风险越大，选择3个多点即可
        stock_list = list(df.index)
        # 买入
        if len(context.portfolio.positions) == 0:
            buy_str = ''
            for stock in stock_list:
                buy_str += "%s%s;"%(stock, get_security_info(stock).display_name)
            send_message('下手股票：%s '%(buy_str))
            log.info('下手股票：%s '%(buy_str))
            for s in stock_list:
                order_target_value(s, context.portfolio.total_value/len(stock_list))
                print( '买入', [get_security_info(s, date).display_name, s])
                print('———————————————————————————————————')



def sell1(context):
    
    # 基础信息
    date = transform_date(context.previous_date, 'str')
    current_data = get_current_data()
    
    # 根据时间执行不同的卖出策略
    for s in list(context.portfolio.positions):
        if ((context.portfolio.positions[s].closeable_amount != 0) and (current_data[s].last_price < current_data[s].high_limit) and (current_data[s].last_price > context.portfolio.positions[s].avg_cost)):
            order_target_value(s, 0)
            print( '止盈卖出', [get_security_info(s, date).display_name, s])
            print('———————————————————————————————————')
                
                
def sell2(context):
    
    # 基础信息
    date = transform_date(context.previous_date, 'str')
    current_data = get_current_data()
    
    # 根据时间执行不同的卖出策略
    for s in list(context.portfolio.positions):
        if ((context.portfolio.positions[s].closeable_amount != 0) and (current_data[s].last_price < current_data[s].high_limit)):
            order_target_value(s, 0)
            print( '止损卖出', [get_security_info(s, date).display_name, s])
            print('———————————————————————————————————')


############################################################################################################################################################################

# 处理日期相关函数
def transform_date(date, date_type):
    if type(date) == str:
        str_date = date
        dt_date = dt.datetime.strptime(date, '%Y-%m-%d')
        d_date = dt_date.date()
    elif type(date) == dt.datetime:
        str_date = date.strftime('%Y-%m-%d')
        dt_date = date
        d_date = dt_date.date()
    elif type(date) == dt.date:
        str_date = date.strftime('%Y-%m-%d')
        dt_date = dt.datetime.strptime(str_date, '%Y-%m-%d')
        d_date = date
    dct = {'str':str_date, 'dt':dt_date, 'd':d_date}
    return dct[date_type]

def get_shifted_date(date, days, days_type='T'):
    #获取上一个自然日
    d_date = transform_date(date, 'd')
    yesterday = d_date + dt.timedelta(-1)
    #移动days个自然日
    if days_type == 'N':
        shifted_date = yesterday + dt.timedelta(days+1)
    #移动days个交易日
    if days_type == 'T':
        all_trade_days = [i.strftime('%Y-%m-%d') for i in list(get_all_trade_days())]
        #如果上一个自然日是交易日，根据其在交易日列表中的index计算平移后的交易日        
        if str(yesterday) in all_trade_days:
            shifted_date = all_trade_days[all_trade_days.index(str(yesterday)) + days + 1]
        #否则，从上一个自然日向前数，先找到最近一个交易日，再开始平移
        else: #否则，从上一个自然日向前数，先找到最近一个交易日，再开始平移
            for i in range(100):
                last_trade_date = yesterday - dt.timedelta(i)
                if str(last_trade_date) in all_trade_days:
                    shifted_date = all_trade_days[all_trade_days.index(str(last_trade_date)) + days + 1]
                    break
    return str(shifted_date)

def join_date_time(date_str, time_str):
    local_str = '%s %s'%(date_str,time_str)
    return(local_str)

# 过滤函数
def filter_new_stock(initial_list, date, days=250):
    d_date = transform_date(date, 'd')
    return [stock for stock in initial_list if d_date - get_security_info(stock).start_date > dt.timedelta(days=days)]

def filter_st_pause_stock(initial_list, date):
    current_data = get_current_data()
    return [stock for stock in initial_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name
            and not current_data[stock].paused]


def filter_kcbj_stock(initial_list):
    return [stock for stock in initial_list if stock[0] != '4' and stock[0] != '8' and stock[:2] != '68']


# 每日初始股票池
def prepare_stock_list(date): 
    initial_list = get_all_securities('stock', date).index.tolist()
    #过滤市值大的股票
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_new_stock(initial_list, date)
    initial_list = filter_st_pause_stock(initial_list, date)
    return initial_list

# 筛选出某一日涨停的股票
def get_hl_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False)
    df = df.dropna() #去除停牌
    hl_list = df[df['close'] == df['high_limit']].code.tolist()
    return hl_list


# 计算涨停数
def get_hl_count_df(hl_list, date, watch_days):
    # 获取watch_days的数据
    df = get_price(hl_list, end_date=date, frequency='daily', fields=['low','close','high_limit'], count=watch_days, panel=False, fill_paused=False, skip_paused=False)
    df.index = df.code
    # 利用 pandas 的函数计算涨停与一字涨停数
    hl_count = (df['close'] == df['high_limit']).groupby(df.index).sum().astype(int)
    extreme_hl_count = (df['low'] == df['high_limit']).groupby(df.index).sum().astype(int)
    #创建df记录
    output_df = pd.DataFrame({'count': hl_count, 'extreme_count': extreme_hl_count}).loc[hl_list]
    return output_df


# 计算连板数
'''def get_continue_count_df(hl_list, date, watch_days):
    df_list = []
    for d in range(2, watch_days+1):
        HLC = get_hl_count_df(hl_list, date, d)
        CHLC = HLC[HLC['count'] == d]
        df_list.append(CHLC)
    ccd = pd.concat(df_list) if df_list else pd.DataFrame()
    if not ccd.empty:
        stock_list = ccd.index.unique()
        ccd_list = []
        for s in stock_list:
            tmp = ccd.loc[[s]]
            if len(tmp) > 1:
                M = tmp['count'].max()
                tmp = tmp[tmp['count'] == M]
            ccd_list.append(tmp)
        if ccd_list:
            ccd = pd.concat(ccd_list)   
            ccd.sort_values(by='count', ascending=False, inplace=True)
    return ccd'''
    
def get_continue_count_df(hl_list, date, watch_days):
    df_list = []
    for d in range(2, watch_days+1):
        HLC = get_hl_count_df(hl_list, date, d)
        CHLC = HLC[HLC['count'] == d]
        df_list.append(CHLC)
    ccd = pd.concat(df_list) if df_list else pd.DataFrame()
    if not ccd.empty:
        ccd = ccd.sort_values(by='count', ascending=False).groupby(level=0).head(1)
    return ccd
    
# 计算股票处于一段时间内相对位置
def get_relative_position_df(stock_list, date, watch_days):
    if stock_list:
        df = get_price(stock_list, end_date=date, fields=['high', 'low', 'close'], count=watch_days, fill_paused=False, skip_paused=False, panel=False).dropna()
        close = df.groupby('code')['close'].last()
        high = df.groupby('code')['high'].max()
        low = df.groupby('code')['low'].min()
        result = pd.DataFrame({
            'rp': (close - low) / (high - low)
        }, index=close.index)
    else:
        result = pd.DataFrame(columns=['rp'])
    return result

# 筛选出某一日某一个时间之前涨停的股票
def get_hl_stock_at_time(initial_list, date, end_time):
    hl_list = []
    if(len(initial_list)>0):
        end_str = join_date_time(date, end_time)
        df = get_price(initial_list, end_date=end_str, frequency='1m', fields=['close','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False)
        df = df.dropna() #去除停牌
        df = df[df['close'] == df['high_limit']]
        hl_list = list(df.code)
    return hl_list
    
#过滤最近一段时间有跌停的股票
def filter_low_limits(stock_list, date, N):
    df = get_price(stock_list, end_date=date, frequency='daily', fields=['close', 'low_limit'], count=N, panel=False, fill_paused=False, skip_paused=False)
    df = df.dropna() #去除停牌
    df = df[df['close'] == df['low_limit']]
    ll_list = list(df.code)
    stock_list = [s for s in stock_list if s not in ll_list]
    return(stock_list)
