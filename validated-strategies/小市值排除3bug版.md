# Small-Cap Excluding 3 Bugs

| Metric | Value |
|--------|-------|
| Annual Return | 81.77% |
| Max Drawdown | 18.26% |
| Sharpe Ratio | 2.425 |
| Source File | `15小市值排除3个bug版，22年至今收益506.txt` |

## Strategy Logic

Small-cap stock rotation strategy with three bug fixes applied to the original version.

## Why It Works

- Small-cap premium in A-share market provides consistent alpha
- Bug fixes likely address data look-ahead, survivorship bias, or execution timing
- High return with controlled drawdown for a small-cap strategy

## Optimization Ideas

1. **Identify the 3 bugs**: Document what the original bugs were for future reference
2. **Add regime filter**: Small-cap strategies suffer during market stress; add volatility/VIX filter
3. **Liquidity constraint**: Ensure minimum daily turnover to avoid slippage in live trading
4. **Factor timing**: Track small-cap factor cycle; reduce exposure during value rotation periods
