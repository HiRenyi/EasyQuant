# VWAP 偏离信号 — 最强种子因子

`rank((vwap - close) / (close + 0.0001))` 系列是目前发现的最强种子信号。

## 指标
- hs300: fitness=0.955, Sharpe=1.659
- 加入 decay_linear 包裹后进一步提升

## 应用
作为新方向探索的基准种子和交叉组合素材。
