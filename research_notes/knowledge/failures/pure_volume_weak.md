# 纯量信号 IC 接近零

不含价格成分的纯成交量信号（如 rank(volume/adv20)）IC 接近零，无预测力。

## 证据
- rank(volume / ts_mean(volume, 20)) → IC ~0.001
- 量必须与价格信号交互才有效

## 教训
量价因子必须包含价格维度（close, vwap, returns）。
