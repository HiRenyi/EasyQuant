# Four Stirrers Strategy

| Metric | Value |
|--------|-------|
| Annual Return | 58.68% |
| Max Drawdown | 18.78% |
| Sharpe Ratio | 1.934 |
| Source File | `5四大搅屎棍策略.txt` |

## Strategy Logic

A multi-strategy portfolio named humorously after "four stirrers" (搅屎棍), combining four different sub-strategies to achieve diversification.

## Why It Works

- Multi-strategy approach reduces single-strategy risk
- Good balance of return (58.68%) and drawdown (18.78%)
- Different sub-strategies likely have low correlation

## Optimization Ideas

1. **Document the four sub-strategies**: Each component strategy should be documented separately
2. **Correlation analysis**: Track inter-strategy correlation over time
3. **Dynamic weighting**: Adjust weights based on recent factor performance
4. **Add a 5th strategy**: If any sub-strategy underperforms, replace with a new candidate
