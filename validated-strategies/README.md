# 已验证策略

> **Forked from** [Miasyster/QuantGPT](https://github.com/Miasyster/QuantGPT) — Agent 驱动的 LLM 量化因子研究引擎。
> 本项目在原始基础上扩展了聚宽 (JoinQuant) 自动回测、批量提交工具，以及经过回测验证的策略库。
> 感谢原作者的优秀基础。

聚宽 (JoinQuant) 回测，周期：2025-01-01 ~ 2025-12-31，初始资金 100 万。

共 28 个完成回测且结果有效的策略，按夏普比率排序。

**注意**：此处代码为实际通过聚宽回测的修改版本（已去除原始聚宽注释，保留核心逻辑），非原始聚宽文章克隆代码。

## 策略总览（按夏普排序）

| # | 策略 | 年化收益 | 最大回撤 | 夏普 | 代码 | 文档 |
|---|------|:--------:|:--------:|:----:|------|------|
| 1 | [首板高开-低开-弱转强混合策略](code/首板高开-低开-弱转强混合策略.py) | **158.72%** | 43.97% | **2.62** | [code](code/首板高开-低开-弱转强混合策略.py) | [docs](first-board-mixed-strategy.md) |
| 2 | [子账户多策略分仓](code/子账户多策略分仓.py) | **81.77%** | 18.26% | **2.43** | [code](code/子账户多策略分仓.py) | [docs](sub-account-multi-strategy.md) |
| 3 | [小市值排除3bug版](code/小市值排除3bug版.py) | **81.77%** | 18.26% | **2.43** | [code](code/小市值排除3bug版.py) | [docs](small-cap-exclude-bugs.md) |
| 4 | [基本面01+RSI择时](code/基本面01+RSI择时.py) | **64.30%** | 14.75% | **2.41** | [code](code/基本面01+RSI择时.py) | [docs](fundamental-rsi-timing.md) |
| 5 | [干积分-量化框架](code/干积分-量化框架.py) | **60.04%** | 23.29% | **2.33** | [code](code/干积分-量化框架.py) | [docs](earnings-points-framework.md) |
| 6 | [稳健型ETF](code/稳健型ETF.py) | **22.16%** | **3.08%** | **2.29** | [code](code/稳健型ETF.py) | [docs](stable-etf-strategy.md) |
| 7 | [国九小市值](code/国九小市值.py) | **74.84%** | 21.23% | **2.21** | [code](code/国九小市值.py) | [docs](guojiu-small-cap.md) |
| 8 | [高股息价投](code/高股息价投.py) | **51.50%** | 16.65% | **2.17** | [code](code/高股息价投.py) | [docs](dividend-value-strategy.md) |
| 9 | [四大搅屎棍](code/四大搅屎棍.py) | **58.68%** | 18.78% | **1.93** | [code](code/四大搅屎棍.py) | [docs](four-stirrers-strategy.md) |
| 10 | [趋势筛选ETF轮动](code/趋势筛选ETF轮动.py) | **41.50%** | 12.52% | **1.83** | [code](code/趋势筛选ETF轮动.py) | [docs](trend-filter-etf-rotation.md) |

## 全部策略

| # | 策略 | 年化收益 | 最大回撤 | 夏普 | 代码 |
|---|------|:--------:|:--------:|:----:|------|
| 11 | [ETF动量EPO](code/ETF动量EPO.py) | 38.93% | 15.72% | 1.59 | [code](code/ETF动量EPO.py) |
| 12 | [首板低开优化版](code/首板低开优化版.py) | 38.93% | 27.28% | 1.19 | [code](code/首板低开优化版.py) |
| 13 | [安全摸狗](code/安全摸狗.py) | 33.20% | 19.98% | 1.19 | [code](code/安全摸狗.py) |
| 14 | [大市值价值低回撤](code/大市值价值低回撤.py) | 13.59% | 5.48% | 1.01 | [code](code/大市值价值低回撤.py) |
| 15 | [白马股攻防转换](code/白马股攻防转换.py) | 21.19% | 23.27% | 0.86 | [code](code/白马股攻防转换.py) |
| 16 | [指数ETF动量轮动](code/指数ETF动量轮动.py) | 28.34% | 20.43% | 0.72 | [code](code/指数ETF动量轮动.py) |
| 17 | [蛇皮走位小市值](code/蛇皮走位小市值.py) | 16.08% | 14.63% | 0.74 | [code](code/蛇皮走位小市值.py) |
| 18 | [追首板涨停](code/追首板涨停.py) | 57.52% | 63.10% | 1.07 | [code](code/追首板涨停.py) |
| 19 | [国九条中小板微盘](code/国九条中小板微盘.py) | 74.84% | 21.23% | 2.21 | [code](code/国九条中小板微盘.py) |
| 20 | [十年52倍年化59](code/十年52倍年化59.py) | 60.04% | 23.29% | 2.33 | [code](code/十年52倍年化59.py) |
| 21 | [低风险中等收益](code/低风险中等收益.py) | 26.71% | 12.98% | 2.01 | [code](code/低风险中等收益.py) |
| 22 | [五年15倍年化79](code/五年15倍年化79.py) | 21.95% | 16.57% | 1.01 | [code](code/五年15倍年化79.py) |
| 23 | [首板低开原版](code/首板低开原版.py) | 40.16% | 49.70% | 0.95 | [code](code/首板低开原版.py) |
| 24 | [ROIC中等市值](code/ROIC中等市值.py) | 9.43% | 9.36% | 0.35 | [code](code/ROIC中等市值.py) |
| 25 | [趋势筛选ETF轮动10倍](code/趋势筛选ETF轮动10倍.py) | 41.50% | 12.52% | 1.83 | [code](code/趋势筛选ETF轮动10倍.py) |
| 26 | [Gyro小市值因子匹配](code/Gyro小市值因子匹配.py) | 47.69% | 17.26% | 1.49 | [code](code/Gyro小市值因子匹配.py) |
| 27 | [Debug多标的ETF](code/Debug多标的ETF.py) | 14.13% | 28.56% | 0.36 | [code](code/Debug多标的ETF.py) |
| 28 | [大市值价值优化](code/大市值价值优化.py) | -13.12% | 20.99% | -0.80 | [code](code/大市值价值优化.py) |

## 目录结构

```
validated-strategies/
├── README.md                    # 本文件
├── code/                        # 策略源代码（28 个，实际回测修改版）
│   ├── 首板高开-低开-弱转强混合策略.py
│   ├── 子账户多策略分仓.py
│   └── ...
├── first-board-mixed-strategy.md    # 详细分析文档（Top 10）
├── sub-account-multi-strategy.md
└── ...
```
