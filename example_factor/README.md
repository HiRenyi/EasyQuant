# QuantGPT — Validated Factor Results

Agent-driven factor research engine. Factors below were discovered, optimized, and submitted to WorldQuant BRAIN through QuantGPT's autonomous research loop.

All factor expressions use WorldQuant BRAIN operator standard and are directly submittable.

---

## Factor 1: 短窗口价量背离 (5 日)

```
-1 * rank(ts_corr(close, volume, 5))
```

| Market | Sharpe | Turnover | Fitness | IS PASS |
|--------|--------|----------|---------|---------|
| A 股 HS300 | 1.42 | — | — | — |
| 美股 TOP3000 | 1.73 | 48.27% | 0.60 | 6/7 |

![WQ BRAIN PnL](2-1.png)
![WQ BRAIN IS Summary](2-2.png)

---

## Factor 2: 中窗口价量背离 (10 日)

```
-1 * rank(ts_corr(close, volume, 10))
```

| Market | Sharpe | Turnover | Fitness | IS PASS |
|--------|--------|----------|---------|---------|
| A 股 HS300 | 0.66 | — | — | — |
| 美股 TOP3000 | 0.91 | 31.21% | 0.30 | 4/7 |

![WQ BRAIN PnL](1-1.jpg)
![WQ BRAIN IS Summary](1-2.jpg)

---

## Factor 3: 双价量背离 (close × high)

```
rank(-1 * ts_corr(close, volume, 5)) * rank(-1 * ts_corr(high, volume, 10))
```

| Market | Sharpe | Turnover | Fitness | IS PASS |
|--------|--------|----------|---------|---------|
| A 股 HS300 | 0.87 | — | — | — |
| 美股 TOP3000 | 1.20 | 37.56% | 0.41 | 6/7 |

![WQ BRAIN PnL](3-1.png)
![WQ BRAIN IS Summary](3-2.png)

---

## Factor 4: VWAP 衰减反转 — **已正式提交 BRAIN** (alpha_id: `78aAQjoL`)

```
-1 * rank(ts_decay_linear(close / vwap, 10))
```

| Item | Value |
|------|-------|
| Sharpe | **1.69** |
| Fitness | **1.07** (≥ 1.0 PASS) |
| Turnover | 46.14% |
| Returns | 18.63% |
| IS Tests | **全部通过** |
| Status | **Submitted** |

突破关键：将中性化从 SUBINDUSTRY 切到 MARKET，Fitness 从 0.88 → 1.07。

![WQ BRAIN PnL — VWAP Decay Reversal](4-1.png)
![WQ BRAIN IS Summary — VWAP Decay Reversal](4-2.png)

---

## Summary

| Factor | Expression | WQ Sharpe | IS PASS | Status |
|--------|-----------|-----------|---------|--------|
| 短窗口价量背离 | `-1 * rank(ts_corr(close, volume, 5))` | 1.73 | 6/7 | Validated |
| 中窗口价量背离 | `-1 * rank(ts_corr(close, volume, 10))` | 0.91 | 4/7 | Validated |
| 双价量背离 | `rank(-1*ts_corr(close,volume,5))*rank(-1*ts_corr(high,volume,10))` | 1.20 | 6/7 | Validated |
| VWAP 衰减反转 | `-1 * rank(ts_decay_linear(close / vwap, 10))` | 1.69 | 7/7 | **Submitted** |

![Dashboard](dashboard.png)
