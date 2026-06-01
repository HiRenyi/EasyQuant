# 克隆自聚宽文章：https://www.joinquant.com/post/48789
# 标题：低风险中等收益策略
# 作者：Gyro^.^

import pandas as pd
import json

def initialize(context):
    # setting system
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    # setting strategy
    run_daily(iUpdate, 'before_open')
    run_daily(iTrader, '9:35')
    run_daily(iReport, 'after_close')
    g.days = 0 # day counter

def iUpdate(context):
    # parameters
    nposition = 100 # number of positions
    nchoice = 30
    # daily update
    g.days = g.days + 1
    g.stocks = _choice_small(context, nchoice)
    g.funds = _choice_funds(context)
    g.position_size = 1.0/nposition * context.portfolio.total_value

def iTrader(context):
    # load data
    stocks = g.stocks
    funds = g.funds 
    position_size = g.position_size
    cash_size = 5 * position_size
    cdata = get_current_data()
    # sell
    choice = stocks + funds
    for s in context.portfolio.positions:
        if cdata[s].paused:
            continue
        if s not in choice:
            log.info('sell', s, cdata[s].name)
            order_target(s, 0, MarketOrderStyle(0.99*cdata[s].last_price))
    # buy stocks
    for s in stocks:
        if context.portfolio.available_cash < position_size:
            break # 现金耗尽，中止
        if cdata[s].paused:
            continue
        if s not in context.portfolio.positions:
            log.info('buy', s, cdata[s].name)
            value = max(position_size, 100*cdata[s].last_price)
            order_value(s, value, MarketOrderStyle(1.01*cdata[s].last_price))
    # buy funds
    for s in funds:
        if context.portfolio.available_cash < cash_size:
            break # 现金耗尽，中止
        if not cdata[s].paused:
            log.info('save', s, cdata[s].name)
            order_value(s, position_size, MarketOrderStyle(cdata[s].last_price))

def iReport(context):
    # table of positions
    cdata = get_current_data()
    tvalue = context.portfolio.total_value
    ptable = pd.DataFrame(columns=['amount', 'value', 'weight', 'name'])
    for s in context.portfolio.positions:
        ps = context.portfolio.positions[s]
        ptable.loc[s] = [ps.total_amount, int(ps.value), 100*ps.value/tvalue, cdata[s].name]
    ptable = ptable.sort_values(by='weight', ascending=False)
    # daily report
    pd.set_option('display.max_rows', None)
    log.info('  positions', len(ptable), '\n', ptable.head())
    log.info('  total win %i, return %.2f%%', \
            int(tvalue - context.portfolio.inout_cash), 100*context.portfolio.returns)
    log.info('  total value %.2f, cash %.2f', \
            context.portfolio.total_value/10000, context.portfolio.available_cash/10000)
    log.info('running days', g.days)

def _choice_small(context, nchoice):
    # parameters
    index = '399317.XSHE'
    # stocks
    dt_now = context.current_dt.date()
    stocks = get_index_stocks(index, dt_now)
    # non-ST
    cdata = get_current_data()
    stocks = [s for s in stocks if not cdata[s].is_st]
    # small stocks, 10%
    m = int(0.1*len(stocks))
    df = get_fundamentals(query(
            valuation.code,
            valuation.market_cap,
            valuation.pb_ratio,
            indicator.inc_return,
            indicator.ocf_to_revenue,
        ).filter(
            valuation.code.in_(stocks),
        ).order_by(valuation.market_cap.asc()
        ).limit(m)
        ).dropna().set_index('code')
    # qualify, 三正
    df = df[(df.pb_ratio > 0) & (df.inc_return > 0) & (df.ocf_to_revenue > 0)]
    # choice
    n = int(1.2 * nchoice) # buffer 20%
    stocks = df.head(n).index.tolist()
    # united
    stocks_0 = [s for s in stocks if s in context.portfolio.positions]
    stocks_1 = [s for s in stocks if s not in context.portfolio.positions]
    choice = (stocks_0 + stocks_1)[:nchoice]
    # report
    df = df[['market_cap']].loc[choice]
    df['name'] = [cdata[s].name for s in df.index]
    log.info('small-quality stocks', len(choice), '\n', df.head())
    # reuslt
    return choice

def _choice_funds(context):
    # load funds
    #funds = json.loads(read_file('funds'))
    funds = ['511220.XSHG', '518880.XSHG', '513500.XSHG']
    # filter
    cdata = get_current_data()
    funds = [s for s in funds if not cdata[s].paused]
    if len(funds) == 0:
        funds = ['000012.XSHG'] # default
    # results
    return funds
# end