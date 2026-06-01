# Dividend Value Strategy

| Metric | Value |
|--------|-------|
| Annual Return | 51.50% |
| Max Drawdown | 16.65% |
| Sharpe Ratio | 2.168 |
| Source File | `4高股息低市盈率高增长的价投策略.txt` |

## Strategy Logic

Classic value investing: select stocks with high dividend yield, low P/E ratio, and high earnings growth.

## Why It Works

- Three-factor approach (dividend + value + growth) provides robust stock selection
- Low drawdown (16.65%) reflects defensive nature of value stocks
- Sortino ratio 3.082 - downside deviation is minimal

## Optimization Ideas

1. **Dynamic P/E threshold**: Adjust P/E cutoff based on market average (relative valuation)
2. **Growth quality**: Add ROIC or FCF yield to filter out accounting-driven growth
3. **Dividend sustainability**: Check payout ratio; avoid companies with unsustainable dividends
4. **Earnings revision factor**: Add analyst estimate revisions as a timing signal
5. **Market cap neutrality**: Ensure performance isn't just small-cap beta in disguise
