# Guojiu Small-Cap Strategy

| Metric | Value |
|--------|-------|
| Annual Return | 74.84% |
| Max Drawdown | 21.23% |
| Sharpe Ratio | 2.207 |
| Source File | `6国九小市值策略【年化100.5】.txt` |

## Strategy Logic

Small-cap strategy adapted to the new "Guojiu" (国九条) regulatory framework. The 2024 policy changes affected dividend requirements and ST rules, which this strategy incorporates.

## Why It Works

- Policy-aware design avoids stocks that would be penalized under new rules
- Small-cap premium combined with regulatory compliance filter
- High return (74.84%) with Sharpe > 2

## Optimization Ideas

1. **ST rule adaptation**: The policy landscape continues to evolve; monitor for further changes
2. **Dividend factor**: Add dividend yield as a positive factor (aligned with policy direction)
3. **Risk management**: The 21.23% drawdown is manageable but could be reduced with trend filter
4. **Backtest across regimes**: Test on 2022-2024 data to verify policy adaptation works
