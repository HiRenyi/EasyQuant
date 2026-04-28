# 低波因子族整体证伪（含组合因子）

**标签**: overfitting, temporal, volume, low-volatility, dead-end

整个低波因子族 `(high-low)/close` 及其变体在 A 股不具备稳健截面预测能力。[Agent+DS 共识]

## 证据链
- 复合因子 `rank(-ts_mean((high-low)/close,5) * adv20/volume)`: hs300 近期 A级(2.749)，全样本 B级(1.243)，样本外 C级(0.693)
- 纯低波 `rank(-(high-low)/close)`: hs300 全样本 Fitness 0.795 / Sharpe 1.240，但子区间崩塌（2021-2022: 0.073, 2023-2024: 0.349）
- 跨市场失效: csi500 Sharpe 0.257, csi1000 Sharpe 0.271
- 样本外失效: 2018-2020 Sharpe 0.184
- adv20/volume 独立无效 (Fitness -0.022)
- 市值交互排除: /market_cap → Fitness 0.006

## 教训
- 全样本看起来不错的因子必须做子区间验证
- 稳健因子最低要求: 多数2年子区间 Sharpe > 0.5 且跨市场保留一半信号
- adv20/volume 增强效应是虚假交互
- 复杂乘法组合比简单因子更容易过拟合
- DS评审盲点：未做行业中性化、IC序列、交易成本检验
