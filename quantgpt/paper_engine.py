"""Paper trading engine — daily settlement for simulated portfolios.

Architecture follows ai-quant-research-execution PaperTradingEngine:
- Explicit cash tracking (NAV = cash + market_value)
- Rebalance day vs hold day distinction
- Buy at open price, value at close price
- Detailed cost model: commission + stamp tax + slippage
- Suspended stock carry-forward
"""

import logging
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .expression_parser import parse_expression
from .market_data import MarketDataFetcher, get_universe
from .models import PaperOrder, PaperSnapshot, PaperStrategy

logger = logging.getLogger(__name__)

MIN_COMMISSION = 5.0  # Minimum commission per trade (CNY)


async def run_daily_settlement(db: AsyncSession):
    """Run daily settlement for all active paper strategies."""
    result = await db.execute(
        select(PaperStrategy).where(PaperStrategy.status == "active")
    )
    strategies = result.scalars().all()
    if not strategies:
        logger.info("Paper: no active strategies")
        return

    logger.info(f"Paper: settling {len(strategies)} active strategies")
    for strategy in strategies:
        try:
            await _settle_strategy(db, strategy)
        except Exception as e:
            logger.error(f"Paper: strategy {strategy.id} settlement failed: {e}")
    await db.commit()
    logger.info("Paper: daily settlement complete")


def _normalize_positions(positions: dict | None) -> dict:
    """Convert old format {code: shares} to new {code: {shares, entry_price, entry_date}}."""
    if not positions:
        return {}
    result = {}
    for code, val in positions.items():
        if isinstance(val, dict):
            result[code] = val
        else:
            result[code] = {"shares": int(val), "entry_price": 0.0, "entry_date": ""}
    return result


async def _settle_strategy(db: AsyncSession, strategy: PaperStrategy):
    """Settle one strategy: mark-to-market or rebalance."""
    from zoneinfo import ZoneInfo
    CST = ZoneInfo("Asia/Shanghai")
    today = datetime.now(CST).strftime("%Y-%m-%d")

    # Idempotent: skip if already settled today
    existing = await db.execute(
        select(PaperSnapshot).where(
            PaperSnapshot.strategy_id == strategy.id,
            PaperSnapshot.date == today,
        )
    )
    if existing.scalar_one_or_none():
        return

    # Load previous state
    last_snap = await _get_latest_snapshot(db, strategy.id)
    prev_positions = _normalize_positions(last_snap.positions if last_snap else None)
    prev_cash = last_snap.cash if (last_snap and last_snap.cash is not None) else strategy.initial_capital
    prev_nav = last_snap.portfolio_value if last_snap else strategy.initial_capital

    # Determine rebalance or hold
    should_rebalance = False
    if strategy.next_rebalance_date and today >= strategy.next_rebalance_date or not strategy.last_rebalance_date:
        should_rebalance = True

    if should_rebalance:
        await _settle_rebalance_day(db, strategy, today, prev_nav, prev_cash, prev_positions)
    else:
        await _settle_hold_day(db, strategy, today, prev_nav, prev_cash, prev_positions)


async def _settle_hold_day(
    db: AsyncSession, strategy: PaperStrategy,
    today: str, prev_nav: float, prev_cash: float, prev_positions: dict,
):
    """Non-rebalance day: mark-to-market only, no trades."""
    if not prev_positions:
        _record_snapshot(db, strategy, today, prev_nav, prev_cash, 0.0, 0.0, {})
        return

    fetcher = MarketDataFetcher()
    symbols = list(prev_positions.keys())
    close_prices = _fetch_close_prices(fetcher, symbols, today)

    market_value = sum(
        pos["shares"] * close_prices.get(sym, pos.get("entry_price", 0))
        for sym, pos in prev_positions.items()
    )
    nav = prev_cash + market_value
    daily_return = (nav / prev_nav - 1) if prev_nav > 0 else 0.0

    _record_snapshot(db, strategy, today, nav, prev_cash, market_value, daily_return, prev_positions)
    logger.info(f"Paper [{strategy.id}] {today} HOLD: NAV={nav:.2f}, return={daily_return:.4f}")


async def _settle_rebalance_day(
    db: AsyncSession, strategy: PaperStrategy,
    today: str, prev_nav: float, prev_cash: float, prev_positions: dict,
):
    """Rebalance day: sell old positions, buy new ones from factor ranking."""
    fetcher = MarketDataFetcher()
    comm_rate = strategy.commission_rate or 0.0003
    stamp_rate = strategy.stamp_tax_rate or 0.001
    slip_rate = strategy.slippage_rate or 0.002

    # Compute new target stocks from factor
    stock_codes = get_universe(strategy.universe, date=today)
    lookback_start = pd.Timestamp(today) - pd.Timedelta(days=90)
    market_df = fetcher.fetch_stocks(stock_codes, lookback_start.strftime("%Y-%m-%d"), today)

    if market_df is None or len(market_df) == 0:
        logger.warning(f"Paper: no market data for rebalance on {today}")
        await _settle_hold_day(db, strategy, today, prev_nav, prev_cash, prev_positions)
        return

    # Enrich with fundamentals if needed
    from .fundamental_data import FundamentalDataFetcher, detect_fundamental_vars, enrich_with_fundamentals_rq
    fund_vars = detect_fundamental_vars(strategy.expression)
    if fund_vars:
        sd, ed = lookback_start.strftime("%Y-%m-%d"), today
        rq_result = enrich_with_fundamentals_rq(market_df, fund_vars, stock_codes, sd, ed)
        if rq_result is not None:
            market_df = rq_result
        else:
            ff = FundamentalDataFetcher()
            non_div = fund_vars - {"dividend_yield"}
            if non_div:
                qdf = ff.fetch_fundamentals(stock_codes, sd, ed, non_div)
                if qdf is not None and len(qdf) > 0:
                    market_df = ff.align_to_daily(qdf, market_df, non_div)

    # Compute factor values
    func = parse_expression(strategy.expression)
    market_sorted = market_df.sort_values(["stock_code", "trade_date"])
    try:
        fv = func(market_sorted)
        if isinstance(fv, pd.Series):
            fv.index = market_sorted.index
        market_sorted["_fv"] = fv
    except Exception:
        market_sorted["_fv"] = np.nan

    latest_date = market_sorted["trade_date"].max()
    latest_df = market_sorted[market_sorted["trade_date"] == latest_date].copy()
    if len(latest_df) < 10:
        logger.warning(f"Paper: too few stocks ({len(latest_df)}) for rebalance")
        await _settle_hold_day(db, strategy, today, prev_nav, prev_cash, prev_positions)
        return

    factor_series = latest_df.set_index("stock_code")["_fv"].dropna()
    n_per_group = max(1, len(factor_series) // strategy.n_groups)
    top_stocks = factor_series.nlargest(n_per_group).index.tolist()

    # Get open prices for trading, close prices for valuation
    open_prices = {}
    close_prices = {}
    for code in set(top_stocks) | set(prev_positions.keys()):
        row = latest_df[latest_df["stock_code"] == code]
        if len(row) > 0:
            open_prices[code] = float(row["open"].iloc[0])
            close_prices[code] = float(row["close"].iloc[0])

    # --- Sell all old positions at open ---
    cash = prev_cash
    unsold = {}
    for sym, pos in prev_positions.items():
        price = open_prices.get(sym)
        if price and price > 0:
            sell_value = pos["shares"] * price
            commission = max(sell_value * comm_rate, MIN_COMMISSION)
            stamp_tax = sell_value * stamp_rate
            slippage = sell_value * slip_rate
            net = sell_value - commission - stamp_tax - slippage
            cash += net
            db.add(PaperOrder(
                id=uuid.uuid4(), strategy_id=strategy.id, date=today,
                stock_code=sym, direction="sell", shares=pos["shares"],
                price=price, amount=sell_value,
                commission=commission + stamp_tax, slippage=slippage,
            ))
        else:
            unsold[sym] = pos

    # --- Buy new positions at open ---
    new_positions = {}
    buyable = [c for c in top_stocks if c in open_prices and open_prices[c] > 0]
    if buyable:
        per_stock_cash = cash / len(buyable)
        for code in buyable:
            price = open_prices[code]
            max_shares = int(per_stock_cash / (price * (1 + comm_rate + slip_rate)) / 100) * 100
            if max_shares < 100:
                max_shares = 100
            buy_value = max_shares * price
            commission = max(buy_value * comm_rate, MIN_COMMISSION)
            slippage = buy_value * slip_rate
            total_cost = buy_value + commission + slippage
            cash -= total_cost
            new_positions[code] = {
                "shares": max_shares,
                "entry_price": price,
                "entry_date": today,
            }
            db.add(PaperOrder(
                id=uuid.uuid4(), strategy_id=strategy.id, date=today,
                stock_code=code, direction="buy", shares=max_shares,
                price=price, amount=buy_value,
                commission=commission, slippage=slippage,
            ))

    # Merge unsold (suspended) positions
    for sym, pos in unsold.items():
        if sym not in new_positions:
            new_positions[sym] = pos

    # NAV at close prices
    market_value = sum(
        pos["shares"] * close_prices.get(sym, pos.get("entry_price", 0))
        for sym, pos in new_positions.items()
    )
    nav = cash + market_value
    daily_return = (nav / prev_nav - 1) if prev_nav > 0 else 0.0

    # Update strategy state
    next_date = pd.Timestamp(today) + pd.tseries.offsets.BDay(strategy.holding_period)
    strategy.last_rebalance_date = today
    strategy.next_rebalance_date = next_date.strftime("%Y-%m-%d")

    _record_snapshot(db, strategy, today, nav, cash, market_value, daily_return, new_positions)
    n_trades = len(buyable) + len(prev_positions) - len(unsold)
    logger.info(f"Paper [{strategy.id}] {today} REBALANCE: NAV={nav:.2f}, return={daily_return:.4f}, trades={n_trades}")


def _record_snapshot(
    db: AsyncSession, strategy: PaperStrategy,
    today: str, nav: float, cash: float, market_value: float,
    daily_return: float, positions: dict,
):
    """Persist snapshot and update strategy current_value."""
    db.add(PaperSnapshot(
        id=uuid.uuid4(), strategy_id=strategy.id, date=today,
        portfolio_value=nav, cash=cash, market_value=market_value,
        daily_return=daily_return, positions=positions,
    ))
    strategy.current_value = nav
    strategy.updated_at = datetime.now(timezone.utc)


def _fetch_close_prices(fetcher: MarketDataFetcher, symbols: list[str], date: str) -> dict[str, float]:
    """Fetch close prices for a list of symbols on a given date."""
    if not symbols:
        return {}
    price_df = fetcher.fetch_stocks(symbols, date, date)
    if price_df is None or len(price_df) == 0:
        return {}
    return dict(price_df.groupby("stock_code")["close"].last())


async def _get_latest_snapshot(db: AsyncSession, strategy_id) -> PaperSnapshot | None:
    from sqlalchemy import desc
    result = await db.execute(
        select(PaperSnapshot)
        .where(PaperSnapshot.strategy_id == strategy_id)
        .order_by(desc(PaperSnapshot.date))
        .limit(1)
    )
    return result.scalar_one_or_none()
