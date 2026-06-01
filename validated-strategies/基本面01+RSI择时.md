# Fundamental + RSI Timing

| Metric | Value |
|--------|-------|
| Annual Return | 64.30% |
| Max Drawdown | 14.75% |
| Sharpe Ratio | 2.41 |
| Source File | `80基本面01加RSI择时.txt` |

## Strategy Logic

Combines fundamental stock selection with RSI-based market timing:
- Fundamental factors screen for quality/value stocks
- RSI indicator determines entry/exit timing to avoid buying at overbought levels

## Why It Works

- Two-layer approach: fundamental (slow signal) + technical (fast signal)
- Low drawdown (14.75%) shows RSI timing effectively avoids market tops
- Sharpe 2.41 indicates consistent risk-adjusted returns

## Optimization Ideas

1. **RSI parameter optimization**: Test different RSI periods (14 vs 21) and thresholds
2. **Add volume confirmation**: RSI divergences with volume spikes are more reliable
3. **Multi-factor enhancement**: Combine fundamental with momentum/quality factors
4. **Sector rotation**: Apply RSI timing at sector level, not just individual stocks
5. **Walk-forward testing**: Validate RSI parameters don't overfit to 2025 data
