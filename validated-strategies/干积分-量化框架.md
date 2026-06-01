# Points Framework (Large/Small Cap Switching)

| Metric | Value |
|--------|-------|
| Annual Return | 60.04% |
| Max Drawdown | 23.29% |
| Sharpe Ratio | 2.328 |
| Source File | `9干积分-量化策略简易框架.txt` |

## Strategy Logic

A quantitative framework that switches between large-cap and small-cap exposure based on market regime signals ("points" system).

## Why It Works

- Regime-switching captures the cyclical nature of size factor in A-shares
- Framework approach allows adding new strategies/modules
- Moderate drawdown for the return level achieved

## Optimization Ideas

1. **Regime signal refinement**: Add macro indicators (credit growth, PMI) to switching logic
2. **Transition smoothing**: Gradual rebalancing instead of binary switch to reduce whipsaw
3. **Module library**: Build a library of candidate strategies for the framework to choose from
4. **Position management**: Add cash management rules for extreme market conditions
