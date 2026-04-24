# 比值信号优于乘法和加法

rank(A / (B + epsilon)) 结构在多轮实验中持续优于：
- 乘法: rank(A) * rank(B) — Sharpe 通常 < 0.8
- 加法: rank(A) + rank(B) — Sharpe 上限有限

## 证据
- rank(-ret5 / (vol/adv20 + 0.0001)) → Sharpe 1.452 (hs300)
- rank(-ret5 / (volatility + 0.0001)) → Sharpe 1.169 (hs300)
- rank(-ret5) * rank(-vol/adv20) → Sharpe 0.689 (hs300)

## 应用
设计新因子时，优先使用 rank(signal_A / (signal_B + 0.0001)) 结构。
