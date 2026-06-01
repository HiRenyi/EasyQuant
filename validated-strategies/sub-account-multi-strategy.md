# Sub-Account Multi-Strategy Portfolio

| Metric | Value |
|--------|-------|
| Annual Return | 81.77% |
| Max Drawdown | 18.26% |
| Sharpe Ratio | 2.425 |
| Source File | `12用子账户模拟多策略分仓.txt` |

## Strategy Logic

Simulates multiple sub-accounts running different strategies simultaneously, achieving diversification through strategy-level allocation rather than stock-level allocation.

## Why It Works

- Strategy diversification reduces correlated risk
- Each sub-strategy operates independently with its own risk profile
- Combined effect: high return (81.77%) with moderate drawdown (18.26%)
- Sharpe ratio of 2.43 indicates excellent risk-adjusted returns

## Optimization Ideas

1. **Dynamic rebalancing**: Adjust sub-account weights based on recent performance (momentum or mean-reversion)
2. **Correlation monitoring**: Track inter-strategy correlation; add new strategies when correlation rises
3. **Risk budgeting**: Allocate capital inversely proportional to each strategy's volatility
4. **Circuit breaker**: Pause individual sub-strategies when they exceed individual drawdown limits
