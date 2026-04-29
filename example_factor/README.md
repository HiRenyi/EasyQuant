# QuantGPT — Submitted Factors (WQ BRAIN)

Agent-driven factor research engine. Factors below were discovered, optimized, and submitted to WorldQuant BRAIN through QuantGPT's autonomous research loop. All passed IS tests.

---

## Factor 1: Debt-Momentum Composite — **已正式提交 BRAIN**

```
-1 * rank(ts_av_diff(close, 10)) + rank(debt / enterprise_value)
```

| Item | Value |
|------|-------|
| Sharpe | **1.77** |
| Fitness | **1.26** (≥ 1.0 PASS) |
| Turnover | 39.93% |
| Returns | 20.18% |
| Drawdown | 11.29% |
| Neutralization | Industry |
| IS Tests | **全部通过** |
| Status | **Submitted** |

结合动量反转信号（ts_av_diff）与基本面价值信号（debt/enterprise_value），行业中性化。Fitness 1.26 为目前最高。

![WQ BRAIN PnL — Debt-Momentum Composite](1-1.png)
![WQ BRAIN IS Summary — Debt-Momentum Composite](1-2.png)

---

## Factor 2: VWAP 衰减反转 — **已正式提交 BRAIN**

```
-1 * rank(ts_decay_linear(close / vwap, 10))
```

| Item | Value |
|------|-------|
| Sharpe | **1.69** |
| Fitness | **1.07** (≥ 1.0 PASS) |
| Turnover | 46.14% |
| Returns | 18.63% |
| Drawdown | 13.13% |
| Neutralization | Market |
| IS Tests | **全部通过** |
| Status | **Submitted** |

![WQ BRAIN PnL — VWAP Decay Reversal](2-1.png)
![WQ BRAIN IS Summary — VWAP Decay Reversal](2-2.png)

---

## Factor 3: Returns-Volume Momentum — **已正式提交 BRAIN**

```
-1 * rank(ts_decay_linear(returns * volume / adv20, 5))
```

| Item | Value |
|------|-------|
| Sharpe | **1.60** |
| Fitness | **1.03** (≥ 1.0 PASS) |
| Turnover | 57.87% |
| Returns | 24.15% |
| Drawdown | 11.79% |
| Neutralization | Market |
| IS Tests | **全部通过** |
| Status | **Submitted** |

捕捉收益率与相对成交量（volume/adv20）的衰减加权动量信号。Returns 24.15% 为三个因子中最高。

![WQ BRAIN PnL — Returns-Volume Momentum](3-1.png)
![WQ BRAIN IS Summary — Returns-Volume Momentum](3-2.png)

---

## Summary

| Factor | Expression | WQ Sharpe | WQ Fitness | Returns | IS PASS | Status |
|--------|-----------|-----------|-----------|---------|---------|--------|
| Debt-Momentum Composite | `-1 * rank(ts_av_diff(close, 10)) + rank(debt / enterprise_value)` | 1.77 | 1.26 | 20.18% | 7/7 | **Submitted** |
| VWAP 衰减反转 | `-1 * rank(ts_decay_linear(close / vwap, 10))` | 1.69 | 1.07 | 18.63% | 7/7 | **Submitted** |
| Returns-Volume Momentum | `-1 * rank(ts_decay_linear(returns * volume / adv20, 5))` | 1.60 | 1.03 | 24.15% | 7/7 | **Submitted** |

![Dashboard](dashboard.png)
