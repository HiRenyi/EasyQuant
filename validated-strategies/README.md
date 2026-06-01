# Validated Strategies

Backtested on JoinQuant (聚宽), period: 2025-01-01 ~ 2025-12-31, initial capital: 1M RMB.

All 28 strategies that completed backtest with valid results. Ranked by Sharpe ratio.

## Top Strategies by Sharpe Ratio

| # | Strategy | Annual Return | Max Drawdown | Sharpe | Code | Docs |
|---|----------|---------------|--------------|--------|------|------|
| 1 | first-board-mixed-strategy | 158.72% | 43.97% | 2.62 | [code](code/first-board-mixed-strategy.py) | [docs](first-board-mixed-strategy.md) |
| 2 | sub-account-multi-strategy | 81.77% | 18.26% | 2.43 | [code](code/sub-account-multi-strategy.py) | [docs](sub-account-multi-strategy.md) |
| 3 | small-cap-exclude-bugs | 81.77% | 18.26% | 2.43 | [code](code/small-cap-exclude-bugs.py) | [docs](small-cap-exclude-bugs.md) |
| 4 | fundamental-rsi-timing | 64.30% | 14.75% | 2.41 | [code](code/fundamental-rsi-timing.py) | [docs](fundamental-rsi-timing.md) |
| 5 | earnings-points-framework | 60.04% | 23.29% | 2.33 | [code](code/earnings-points-framework.py) | [docs](earnings-points-framework.md) |
| 6 | stable-etf-strategy | 22.16% | 3.08% | 2.29 | [code](code/stable-etf-strategy.py) | [docs](stable-etf-strategy.md) |
| 7 | guojiu-small-cap | 74.84% | 21.23% | 2.21 | [code](code/guojiu-small-cap.py) | [docs](guojiu-small-cap.md) |
| 8 | dividend-value-strategy | 51.50% | 16.65% | 2.17 | [code](code/dividend-value-strategy.py) | [docs](dividend-value-strategy.md) |
| 9 | four-stirrers-strategy | 58.68% | 18.78% | 1.93 | [code](code/four-stirrers-strategy.py) | [docs](four-stirrers-strategy.md) |
| 10 | trend-filter-etf-rotation | 41.50% | 12.52% | 1.83 | [code](code/trend-filter-etf-rotation.py) | [docs](trend-filter-etf-rotation.md) |

## All Strategies

| # | Strategy | Annual Return | Max Drawdown | Sharpe | Code |
|---|----------|---------------|--------------|--------|------|
| 11 | etf-momentum-epo | 38.93% | 15.72% | 1.59 | [code](code/etf-momentum-epo.py) |
| 12 | first-gap-down-optimized | 38.93% | 27.28% | 1.19 | [code](code/first-gap-down-optimized.py) |
| 13 | safe-mo-gou | 33.20% | 19.98% | 1.19 | [code](code/safe-mo-gou.py) |
| 14 | large-cap-value-low-drawdown | 13.59% | 5.48% | 1.01 | [code](code/large-cap-value-low-drawdown.py) |
| 15 | white-horse-rotation | 21.19% | 23.27% | 0.86 | [code](code/white-horse-rotation.py) |
| 16 | index-etf-momentum-v2 | 28.34% | 20.43% | 0.72 | [code](code/index-etf-momentum-v2.py) |
| 17 | snake-wave-small-cap | 16.08% | 14.63% | 0.74 | [code](code/snake-wave-small-cap.py) |
| 18 | chase-limit-up | 57.52% | 63.10% | 1.07 | [code](code/chase-limit-up.py) |
| 19 | guojiu-small-micro-cap | 74.84% | 21.23% | 2.21 | [code](code/guojiu-small-micro-cap.py) |
| 20 | ten-year-52x-annual-59 | 60.04% | 23.29% | 2.33 | [code](code/ten-year-52x-annual-59.py) |
| 21 | low-risk-medium-return | 26.71% | 12.98% | 2.01 | [code](code/low-risk-medium-return.py) |
| 22 | five-year-15x-annual-79 | 21.95% | 16.57% | 1.01 | [code](code/five-year-15x-annual-79.py) |
| 23 | first-gap-down-original | 40.16% | 49.70% | 0.95 | [code](code/first-gap-down-original.py) |
| 24 | roic-mid-cap | 9.43% | 9.36% | 0.35 | [code](code/roic-mid-cap.py) |
| 25 | trend-filter-etf-rotation-10x | 41.50% | 12.52% | 1.83 | [code](code/trend-filter-etf-rotation-10x.py) |
| 26 | gyro-small-cap-factor | 47.69% | 17.26% | 1.49 | [code](code/gyro-small-cap-factor.py) |
| 27 | debug-multi-etf | 14.13% | 28.56% | 0.36 | [code](code/debug-multi-etf.py) |
| 28 | large-cap-value-optimization | -13.12% | 20.99% | -0.80 | [code](code/large-cap-value-optimization.py) |

## Directory Structure

```
validated-strategies/
├── README.md                    # This file
├── code/                        # Original strategy source code (28 files)
│   ├── first-board-mixed-strategy.py
│   ├── sub-account-multi-strategy.py
│   └── ...
├── first-board-mixed-strategy.md    # Detailed analysis docs (top 10)
├── sub-account-multi-strategy.md
└── ...
```
