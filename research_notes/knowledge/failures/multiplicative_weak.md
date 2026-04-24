# 乘法组合信号弱

rank(A) * rank(B) 乘法组合 Sharpe 一般 < 0.8，显著弱于比值结构。

## 证据
- rank(-ret5) * rank(-vol/adv20) → Sharpe 0.689 (hs300)
- 对比 rank(-ret5 / (vol/adv20 + 0.0001)) → Sharpe 1.452

## 教训
乘法组合丢失了比值结构中的相对大小信息。避免使用。
