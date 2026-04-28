# Architecture

QuantGPT 是 Agent-Driven 的因子研究引擎。核心架构分为六层：Agent 接口、表达式引擎、回测引擎、验证体系、数据管道、进化引擎。

## System Overview

```
LLM Agent (Claude Code / Claude Desktop)
    │
    ├── MCP Tools (10 个)            ← Agent 的工具箱
    │   ├── run_backtest              ← 全市场分组回测
    │   ├── score_factor              ← 0-100 综合评分
    │   ├── diagnose_factor           ← 失败模式诊断
    │   ├── run_anti_overfit          ← 4 项反过拟合检验
    │   ├── run_rolling_validation    ← Walk-forward 验证
    │   ├── validate_expression       ← 语法校验（local/wq 双模式）
    │   ├── list_operators / list_universes
    │   ├── wq_brain_pre_check        ← 自相关预筛
    │   └── wq_brain_batch_submit     ← 批量参数扫描提交
    │
    ├── REST API                      ← 程序化访问
    │   ├── /api/v1/auto_backtest
    │   ├── /api/v1/wq-brain/submit
    │   ├── /api/v1/wq-brain/batch
    │   └── ...
    │
    └── Web UI (monitoring)           ← 任务监控 + 报告查看
```

## 1. Expression Parser (`expression_parser.py`)

将因子表达式字符串解析为可作用于 DataFrame 的函数。

**关键设计**：
- **截面 vs 时序分离**：`rank()`, `zscore()` 按 `trade_date` 分组计算（截面算子）；`ts_mean()`, `ts_corr()` 按 `stock_code` 分组计算（时序算子）
- **递归下降解析**：支持嵌套、运算符优先级、比较/逻辑操作
- **安全约束**：`MAX_DEPTH=100` 防止栈溢出，窗口上限防止 OOM

**算子分类**：

| 类型 | 算子 | 分组方式 |
|------|------|----------|
| 截面 | rank, zscore, scale, sign | 按 trade_date |
| 时序 | ts_mean, ts_std, ts_corr, decay_linear, ... | 按 stock_code |
| 分组 | group_rank, group_zscore, group_neutralize | 按 group × trade_date |
| 技术指标 | ema, sma, rsi, macd, atr, boll_* | 按 stock_code |
| 无状态 | abs, log, sqrt, tanh, sigmoid | 无分组 |
| WQ-only 远程 | vector_neut, trade_when, pasteurize, bucket, vec_*, indneutralize | 仅语法校验 |

**双模式**：`mode="wq"` 支持 WQ BRAIN 全字段（价量 + 基本面 + MDF + 新闻 + 期权 + 关系数据 80+ 字段）和 WQ-only 远程算子（30+），本地做语法校验但不执行计算；`mode="local"` 开放本地可计算的全部算子。

## 2. Backtest Engine (`backtest.py`)

Rank-based 分组回测引擎。

**流程**：
1. 应用因子表达式到全市场 DataFrame
2. 按因子值排序，分为 N 个 quantile 组
3. 在调仓日重新分组，组内等权
4. 计算每组日收益率序列
5. Top 组作为策略收益，Bottom 组作为对照

**关键防偏措施**：
- **Lookahead bias 防护**：`searchsorted(..., side="left")` 延迟组分配到 T+1
- **交易成本**：基于换手率的单边成本模型，在调仓日次日扣除
- **IC 计算**：因子 T 与 forward N-day return 的 Pearson/Spearman 相关
- **API Context Guard**：`_require_api_context()` 强制所有回测走 API 路径

## 3. Validation Suite

三层验证体系，每层独立评估因子质量。

### 3.1 Anti-Overfit (`anti_overfit.py`)

四项统计检验：
- **IC 稳定性**：滚动 IC 的变异系数
- **子样本压力测试**：牛市/熊市/震荡市分段表现
- **安慰剂检验**：随机打乱因子值，验证原始因子是否显著优于随机
- **半衰期估计**：IC 自相关衰减速度

### 3.2 Walk-Forward (`rolling_validator.py`)

滚动窗口验证：
- 数据切分为 train/valid/test 窗口
- 每个窗口独立计算 IC/IR
- 评估样本外衰减程度

### 3.3 WQ BRAIN Simulation (`wq_simulate.py`)

对齐 WorldQuant BRAIN 的回测逻辑：
- Dollar-neutral 多空组合
- Fitness = Sharpe × √(|Returns| / max(Turnover, 0.125))
- IS test compatibility scoring

## 4. Data Pipeline (`market_data.py`)

多数据源 + Parquet 缓存。

```
Request
  │
  ├──▶ Parquet Cache (local, zero-latency)
  │       │ miss
  ├──▶ baostock (free, T+1 delay)
  │       │ miss
  └──▶ akshare (free, same-day data)
```

**缓存策略**：
- 按股票单独缓存为 Parquet 文件：`data/stocks/{code}.parquet`
- 请求时先检查缓存覆盖范围，仅增量获取缺失数据

**股票池**：
- `small_scale`：5 只蓝筹（静态，快速测试用）
- `hs300`：沪深 300（动态获取成分股）
- `csi500`/`csi1000`/`csi2000`：中证系列

## 5. Evolution Engine

### Evolutionary Search (`iteration.py`, `mutation_engine.py`, `crossover_engine.py`)

三阶段因子迭代：
1. **Trajectory Analyzer**：评估因子质量轨迹（探索多样性、收敛速率、稳定性）
2. **Meta-Evolution Selector**：自适应策略选择（EXPLOIT / EXPLORE / RECOMBINE / SIMPLIFY）
3. **Execution**：8 种定向突变 + 高分因子交叉重组

### MCP Server (`mcp_server.py`)

10 个 MCP 工具，供 Claude Code / AI Agent 直接调用：
- `list_operators` / `list_universes`
- `validate_expression` / `run_backtest` / `score_factor`
- `diagnose_factor` / `run_anti_overfit` / `run_rolling_validation`
- `wq_brain_pre_check` / `wq_brain_batch_submit`

### WQ BRAIN Integration (`wq_brain_client.py`)

- 认证 → 模拟 → IS 检查 → 提交，全流程 API
- Alpha Tracker：已提交 alpha 记录 + 自相关预筛
- 批量参数扫描：region × delay × universe × neutralization 网格

## 6. Database

SQLAlchemy 2.0 async ORM，支持 SQLite（默认）和 PostgreSQL。

**核心表**：
- `users` — 用户账户
- `tasks` — 回测任务（状态机：pending → running → completed/failed）
- `reports` — HTML 报告文件记录
- `saved_factors` — 用户保存的因子
- `submitted_alphas` — WQ BRAIN 已提交 alpha 记录
- `paper_strategies` / `paper_snapshots` / `paper_orders` — 模拟盘

## 7. Frontend

React 18 + TypeScript + Vite + Tailwind CSS 4。定位为监控面板，Agent 通过 MCP 工作，Web UI 用于查看结果。

**组件层次**：
```
App
├── ResearchDashboard     # 研究总览（统计/筛选/详情）
├── BacktestForm          # 因子输入 + 参数配置
├── ProgressTracker       # SSE 实时进度
├── ResultsDashboard      # 结果可视化
├── IterationPanel        # AI 迭代优化
├── FactorLibrary         # 因子库管理
├── CompositeBuilder      # 多因子组合
└── PaperTrading          # 模拟盘
```
