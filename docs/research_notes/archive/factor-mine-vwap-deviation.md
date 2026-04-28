# VWAP 偏离因子挖掘

## 目标
以 VWAP 偏离信号（已知最强种子 fitness=0.955, Sharpe=1.659）为核心，系统挖掘 A 级因子（WQ BRAIN: Fitness ≥ 1.0, Sharpe ≥ 1.625）。

## 回测参数
- 宇宙: hs300（优先）/ csi500 / csi1000
- 持仓周期: 5 天
- 分组数: 5
- 日期: 2021-01-01 ~ 2024-12-31（主窗口）
- 基准: hs300
- 稳健性验证: 子区间 + 跨市场 + 样本外（按知识库规则）

## 当前基线
- 最优表达式: `rank((vwap - close) / close)`（种子，待验证）
- hs300: fitness=0.955 | Sharpe=1.659 | Returns=? | Turnover=? | Rating=?

## 实验记录

（即将开始）

## 关键发现

（暂无）

## 下一步可探索的方向

- VWAP 偏离窗口敏感性（当日/3d/5d/10d/20d）
- VWAP 偏离结构变体（ratio/range-normalized/ts_rank）
- 非线性增强（sign_power/decay_linear）
- VWAP 偏离 × 反转交叉（比值结构）
- VWAP 偏离 × 成交量交叉
- 条件门控（趋势/波动率状态）
- 子区间稳定性验证
- 跨市场验证（csi500/csi1000）
- 样本外验证（2018-2020）
