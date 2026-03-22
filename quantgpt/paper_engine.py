"""Paper trading engine — daily settlement for simulated portfolios."""

import logging
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import PaperStrategy, PaperSnapshot, PaperOrder
from .market_data import MarketDataFetcher, get_universe
from .expression_parser import parse_expression

logger = logging.getLogger(__name__)

# Commission rates (A-share)
BUY_COMMISSION = 0.0005   # 0.05%
SELL_COMMISSION = 0.0015  # 0.15% (includes stamp tax)


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

async def _settle_strategy(db: AsyncSession, strategy: PaperStrategy):
    """Settle one strategy: update NAV, rebalance if needed."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Check if already settled today
    existing = await db.execute(
        select(PaperSnapshot).where(
            PaperSnapshot.strategy_id == strategy.id,
            PaperSnapshot.date == today,
        )
    )
    if existing.scalar_one_or_none():
        return

    # Get latest positions
    last_snap = await _get_latest_snapshot(db, strategy.id)
    positions = last_snap.positions if last_snap else {}  # {stock_code: shares}
    prev_value = last_snap.portfolio_value if last_snap else strategy.initial_capital

    # Fetch today's prices for held stocks
    fetcher = MarketDataFetcher()
    held_codes = list(positions.keys()) if positions else []

    # Calculate current portfolio value from held positions
    cash = prev_value  # Start with previous value, adjust below
    portfolio_value = prev_value  # Default if no positions

    if held_codes:
        price_df = fetcher.fetch_stocks(held_codes, today, today)
        if price_df is not None and len(price_df) > 0:
            latest_prices = price_df.groupby("stock_code")["close"].last()
            portfolio_value = 0.0
            for code, shares in positions.items():
                if code in latest_prices.index:
                    portfolio_value += shares * latest_prices[code]
            # Add remaining cash (positions don't use 100% of capital)
            # Cash is tracked implicitly: initial_capital - sum(buy amounts) + sum(sell amounts)

    # Check if rebalance is needed
    should_rebalance = False
    if strategy.next_rebalance_date and today >= strategy.next_rebalance_date:
        should_rebalance = True
    elif not strategy.last_rebalance_date:
        should_rebalance = True  # First rebalance

    new_positions = positions
    if should_rebalance:
        new_positions = await _rebalance(
            db, strategy, portfolio_value, today, fetcher
        )
        portfolio_value = strategy.current_value  # Updated by _rebalance

    # Record snapshot
    daily_return = (portfolio_value / prev_value - 1) if prev_value > 0 else 0.0
    snapshot = PaperSnapshot(
        id=uuid.uuid4(),
        strategy_id=strategy.id,
        date=today,
        portfolio_value=portfolio_value,
        daily_return=daily_return,
        positions=new_positions,
    )
    db.add(snapshot)

    # Update strategy
    strategy.current_value = portfolio_value
    strategy.updated_at = datetime.now(timezone.utc)

    await db.flush()


async def _rebalance(
    db: AsyncSession,
    strategy: PaperStrategy,
    current_value: float,
    today: str,
    fetcher: MarketDataFetcher,
) -> dict:
    """Rebalance: compute factor, select top group, generate orders."""
    # Fetch universe stocks with recent data (60 days lookback for factor calc)
    stock_codes = get_universe(strategy.universe, date=today)
    lookback_start = pd.Timestamp(today) - pd.Timedelta(days=90)
    market_df = fetcher.fetch_stocks(stock_codes, lookback_start.strftime("%Y-%m-%d"), today)

    if market_df is None or len(market_df) == 0:
        logger.warning(f"Paper: no market data for rebalance on {today}")
        return {}

    # Enrich with fundamentals if needed
    from .fundamental_data import detect_fundamental_vars, FundamentalDataFetcher, enrich_with_fundamentals_rq
    fund_vars = detect_fundamental_vars(strategy.expression)
    if fund_vars:
        sd, ed = lookback_start.strftime("%Y-%m-%d"), today
        rq_result = enrich_with_fundamentals_rq(market_df, fund_vars, stock_codes, sd, ed)
        if rq_result is not None:
            market_df = rq_result
        else:
            fund_fetcher = FundamentalDataFetcher()
            non_div = fund_vars - {"dividend_yield"}
            if non_div:
                qdf = fund_fetcher.fetch_fundamentals(stock_codes, sd, ed, non_div)
                if qdf is not None and len(qdf) > 0:
                    market_df = fund_fetcher.align_to_daily(qdf, market_df, non_div)
            if "dividend_yield" in fund_vars:
                div_df = fund_fetcher.fetch_dividend_data(stock_codes, sd, ed)
                if div_df is not None and len(div_df) > 0:
                    market_df = fund_fetcher.align_dividends_to_daily(div_df, market_df)

    # Compute factor on latest date
    func = parse_expression(strategy.expression)
    latest_date = market_df["trade_date"].max()
    latest_df = market_df[market_df["trade_date"] == latest_date].copy()

    if len(latest_df) < 10:
        logger.warning(f"Paper: too few stocks ({len(latest_df)}) for rebalance")
        return {}

    # Need full history for time-series operators
    factor_values = {}
    for code in latest_df["stock_code"].unique():
        stock_data = market_df[market_df["stock_code"] == code].sort_values("trade_date")
        if len(stock_data) < 5:
            continue
        try:
            vals = func(stock_data)
            if hasattr(vals, "iloc"):
                factor_values[code] = vals.iloc[-1]
            else:
                factor_values[code] = float(vals) if np.isfinite(vals) else np.nan
        except Exception:
            continue

    if not factor_values:
        return {}

    # Rank and select top group
    factor_series = pd.Series(factor_values).dropna()
    n_per_group = max(1, len(factor_series) // strategy.n_groups)
    top_stocks = factor_series.nlargest(n_per_group).index.tolist()

    # Get latest prices for target stocks
    target_prices = {}
    for code in top_stocks:
        row = latest_df[latest_df["stock_code"] == code]
        if len(row) > 0:
            target_prices[code] = row["close"].iloc[0]

    if not target_prices:
        return {}

    # Equal weight allocation
    per_stock_value = current_value / len(target_prices)

    # Get current positions
    last_snap = await _get_latest_snapshot(db, strategy.id)
    old_positions = last_snap.positions if last_snap and last_snap.positions else {}

    # Generate sell orders (stocks no longer in top group)
    total_cash = current_value
    new_positions = {}

    for code, shares in old_positions.items():
        if code not in target_prices:
            # Sell
            price = target_prices.get(code)
            if price is None:
                row = latest_df[latest_df["stock_code"] == code]
                price = row["close"].iloc[0] if len(row) > 0 else 0
            if price > 0:
                amount = shares * price
                commission = amount * SELL_COMMISSION
                total_cash += amount - commission  # Not needed since we use current_value
                order = PaperOrder(
                    id=uuid.uuid4(),
                    strategy_id=strategy.id,
                    date=today,
                    stock_code=code,
                    direction="sell",
                    shares=shares,
                    price=price,
                    amount=amount,
                    commission=commission,
                )
                db.add(order)

    # Generate buy orders
    for code, price in target_prices.items():
        if price <= 0:
            continue
        shares = int(per_stock_value / price / 100) * 100  # Round to lots of 100
        if shares <= 0:
            shares = 100  # Minimum 1 lot
        amount = shares * price
        commission = amount * BUY_COMMISSION
        new_positions[code] = shares

        if code not in old_positions or old_positions.get(code, 0) != shares:
            order = PaperOrder(
                id=uuid.uuid4(),
                strategy_id=strategy.id,
                date=today,
                stock_code=code,
                direction="buy",
                shares=shares,
                price=price,
                amount=amount,
                commission=commission,
            )
            db.add(order)

    # Update rebalance dates
    # Update rebalance dates (approximate: add holding_period business days)
    next_date = pd.Timestamp(today) + pd.tseries.offsets.BDay(strategy.holding_period)
    strategy.next_rebalance_date = next_date.strftime("%Y-%m-%d")

    strategy.last_rebalance_date = today

    # Recalculate portfolio value after rebalance
    new_value = sum(
        shares * target_prices.get(code, 0) for code, shares in new_positions.items()
    )
    strategy.current_value = new_value if new_value > 0 else current_value

    return new_positions


async def _get_latest_snapshot(db: AsyncSession, strategy_id) -> PaperSnapshot | None:
    from sqlalchemy import desc
    result = await db.execute(
        select(PaperSnapshot)
        .where(PaperSnapshot.strategy_id == strategy_id)
        .order_by(desc(PaperSnapshot.date))
        .limit(1)
    )
    return result.scalar_one_or_none()
