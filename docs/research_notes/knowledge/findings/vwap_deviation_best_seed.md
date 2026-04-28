# VWAP 偏离信号 — 最强种子因子

`close / vwap` 系列是目前发现的最强种子信号族。

## 最佳变体

**`-1 * rank(ts_decay_linear(close / vwap, 5))`**

### WQ BRAIN 实测 (USA/D1/TOP3000, 2026-04-28)

| IS Test | 值 | 阈值 | 状态 |
|---------|-----|------|------|
| Sharpe | 1.47 | ≥ 1.25 | ✓ PASS |
| Fitness | 0.73 | ≥ 1.0 | ✗ FAIL |
| Turnover | 43.99% | 1%~70% | ✓ PASS |
| Weight | 分散 | ≤ 10% | ✓ PASS |
| Sub-Universe Sharpe | 0.81 | ≥ 0.64 | ✓ PASS |
| Competition | Challenge, IQC 2026 Stage 1 | — | ✓ PASS |

**总计: 6/7 PASS，仅 Fitness 差 0.27**

## 信号逻辑

- `close / vwap < 1` → 收盘价低于成交量加权均价，卖方主导
- `ts_decay_linear(..., 5)` → 近 5 日衰减加权，增强近期信号
- `-1 * rank(...)` → 做多"卖方主导"的股票（反转逻辑）

## 应用

- 作为新方向探索的基准种子和交叉组合素材
- 已保存到因子库作为 example_factor
- 提升 Fitness 的方向：降 Turnover、增 Returns、组合其他信号
