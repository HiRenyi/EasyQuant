# Trend-Filtered ETF Rotation

| Metric | Value |
|--------|-------|
| Annual Return | 41.50% |
| Max Drawdown | 12.52% |
| Sharpe Ratio | 1.83 |
| Source File | `74趋势筛选后相关性最小etf轮动.txt` |

## Strategy Logic

Two-step ETF selection:
1. **Trend filter**: Only include ETFs in an uptrend
2. **Correlation minimization**: Among trending ETFs, select the combination with lowest mutual correlation

## Why It Works

- Trend filter avoids buying into downtrending assets
- Low-correlation selection provides natural diversification
- Drawdown of only 12.52% shows effective risk management

## Optimization Ideas

1. **Trend definition**: Test different trend filters (e.g., price > SMA200, MACD crossover)
2. **Correlation window**: Optimize the lookback period for correlation calculation
3. **Risk parity**: Instead of equal-weight, use risk-parity allocation for the selected ETFs
4. **Rebalance frequency**: Monthly may be too infrequent; test weekly rebalancing
5. **Asset class expansion**: Add commodity, bond, and international ETFs for broader diversification
