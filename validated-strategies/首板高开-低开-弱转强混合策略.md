# First-Board Mixed Strategy (Weak-to-Strong)

| Metric | Value |
|--------|-------|
| Annual Return | 158.72% |
| Max Drawdown | 43.97% |
| Sharpe Ratio | 2.624 |
| Source | [聚宽 post 49499](https://www.joinquant.com/post/49499) |
| Author | 天山灵兔 |

## Strategy Logic

A mixed limit-up board strategy combining three entry patterns:

### 1. First-Board Low-Open (首板低开)
- Stock previously hit limit-up but opened 3-4% lower the next day
- Stock's relative position < 50% (not over-extended)
- Previous day turnover >= 100M RMB
- Auction price ratio between 0.955-0.97

### 2. First-Board High-Open (首板高开)
- Average price increase < 7%, turnover 5.5-20B, market cap 70-520B
- Auction volume ratio >= 3% of previous day
- Open ratio between 1.0-1.06 (moderate gap up)
- Volume breakout above recent resistance (left pressure pattern)

### 3. Weak-to-Strong (弱转强)
- Previous 4 days gain < 28% (not over-heated)
- Previous day close/open ratio > -5%
- Auction volume ratio >= 3%
- Auction price ratio 0.98-1.09

## Entry/Exit Rules

**Entry**: Buy at 09:26 using opening price, equal-weight allocation
**Exit 1** (Take Profit): Sell when price > 1.0 * avg_cost but not at limit-up
**Exit 2** (Stop Loss): Sell when price drops below MA5

## Why It Works

- Captures momentum from limit-up stocks with multiple entry filters
- Volume confirmation ensures institutional participation
- Weak-to-strong pattern catches reversal momentum
- MA5 stop-loss limits downside quickly

## Optimization Ideas

1. **Reduce drawdown**: Add market regime filter (skip when CSI300 < 20-day MA)
2. **Position sizing**: Instead of equal-weight, use volatility-based allocation
3. **Timing refinement**: The 09:26 entry is aggressive; consider splitting into two tranches
4. **Sector filter**: Add sector rotation - avoid sectors in downtrend
5. **Volume threshold tuning**: The 3% auction volume ratio may need dynamic adjustment based on market volume
6. **Backtest period**: Currently only 1 year (2025); validate across 2020-2025 for robustness
