# 低波因子 (high-low)/close 基础 alpha

**标签**: volatility, baseline, robust

`-ts_mean((high-low)/close, 5)` 即"低振幅"因子在 hs300 上有稳定基础 alpha，fitness ~0.8-1.0，Sharpe ~1.0-1.2。

## 经济学解释
低日内振幅（(high-low)/close 小）的股票未来表现较好，与经典低波动异象一致。A股市场该效应在大盘股（hs300）和小盘股（csi1000）中有效，中盘股（csi500）较弱。

## 参数敏感性
- 5日窗口最优，但10日/20日也可接受（与反转因子不同，反转仅5日有效）
- rank 截面标准化是必须的
