# Architecture

QuantGPT 的系统架构分为五层：表达式引擎、回测引擎、验证体系、数据管道、AI 层。

## System Overview

```
User Input (NL / Expression)
        │
        ▼
┌─────────────────────┐     ┌──────────────────┐
│  DeepSeek LLM       │────▶│  Expression       │
│  (optional)         │     │  Parser           │
└─────────────────────┘     │  50+ operators    │
                            └────────┬──────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
            ┌──────────┐    ┌──────────────┐   ┌──────────┐
            │ Backtest  │    │ Anti-Overfit  │   │ WQ BRAIN │
            │ Engine    │    │ 4x Tests      │   │ Simulate │
            └──────────┘    └──────────────┘   └──────────┘
                    │                │                │
                    ▼                ▼                ▼
            ┌──────────────────────────────────────────┐
            │          Scoring & Report                 │
            └──────────────────────────────────────────┘
```

## 1. Expression Parser (`expression_parser.py`)

核心模块，872 行。将因子表达式字符串解析为可作用于 DataFrame 的函数。

**关键设计**：
- **截面 vs 时序分离**：`rank()`, `zscore()` 按 `trade_date` 分组计算（截面算子）；`ts_mean()`, `ts_corr()` 按 `stock_code` 分组计算（时序算子）
- **递归下降解析**：支持嵌套、运算符优先级、比较/逻辑操作
- **安全约束**：`MAX_DEPTH=100` 防止栈溢出，窗口上限防止 OOM

**算子分类**：

| 类型 | 算子 | 分组方式 |
|------|------|----------|
| 截面 | rank, zscore, scale, sign | 按 trade_date |
| 时序 | ts_mean, ts_std, ts_corr, decay_linear, ... | 按 stock_code |
| 技术指标 | ema, sma, rsi, macd, atr, boll_* | 按 stock_code |
| 无状态 | abs, log, sqrt, tanh, sigmoid | 无分组 |

**双模式**：`mode="wq"` 限制为 WorldQuant BRAIN 兼容算子（用于提交前校验），`mode="local"` 开放全部算子。

## 2. Backtest Engine (`backtest.py`)

Rank-based 分组回测引擎，477 行。

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

三级数据源 + Parquet 缓存。

```
Request
  │
  ├──▶ Parquet Cache (local, zero-latency)
  │       │ miss
  ├──▶ baostock (free, T+1 delay)
  │       │ miss
  ├──▶ akshare (free, same-day data)
  │       │ miss
  └──▶ rqdatac (optional, paid, batch API)
```

**缓存策略**：
- 按股票单独缓存为 Parquet 文件：`data/stocks/{code}.parquet`
- 请求时先检查缓存覆盖范围，仅增量获取缺失数据
- 每日 15:10 CST 自动增量更新（akshare → baostock fallback）

**股票池**：
- `small_scale`：5 只蓝筹（静态，快速测试用）
- `hs300`：沪深 300（动态获取成分股）
- `csi500`/`csi1000`/`csi2000`：中证系列

## 5. AI Layer

### LLM Integration

- **DeepSeek**（可选）：自然语言 → 因子表达式翻译
- 表达式修复：验证失败时 LLM 自动尝试修正
- 因子解读：生成经济含义、收益来源、风险提示

### Evolutionary Search (`iteration.py`, `mutation_engine.py`, `crossover_engine.py`)

三阶段因子迭代：
1. **Trajectory Analyzer**：评估因子质量轨迹
2. **Meta-Evolution Selector**：选择策略（EXPLOIT / EXPLORE / RECOMBINE / SIMPLIFY）
3. **Execution**：8 种定向突变 + 遗传重组

### MCP Server (`mcp_server.py`)

8 个 MCP 工具，供 Claude Code / AI Agent 直接调用：
- `list_operators` / `list_universes`
- `validate_expression` / `run_backtest` / `score_factor`
- `diagnose_factor` / `run_anti_overfit` / `run_rolling_validation`

## 6. Database

SQLAlchemy 2.0 async ORM，支持 SQLite（默认）和 PostgreSQL。

**核心表**：
- `users` — 用户账户
- `tasks` — 回测任务（状态机：pending → running → completed/failed）
- `reports` — HTML 报告文件记录
- `saved_factors` — 用户保存的因子
- `feedbacks` — 用户反馈
- `paper_strategies` / `paper_snapshots` / `paper_orders` — 模拟盘

## 7. Frontend

React 18 + TypeScript + Vite + Tailwind CSS 4。

**关键模式**：
- Context API 状态管理（Auth + ColorMode）
- SSE 实时任务进度推送，3 次失败后降级为轮询
- Token 自动刷新 + 401 拦截重试

**组件层次**：
```
App
├── BacktestForm          # 因子输入 + 参数配置
├── ProgressTracker       # SSE 实时进度
├── ResultsDashboard      # 结果可视化
├── IterationPanel        # AI 迭代优化
├── FactorLibrary         # 因子库管理
├── DailySummary          # 每日大盘报告
├── StrategyBacktest      # 策略代码回测
├── CompositeBuilder      # 多因子组合
└── PaperTrading          # 模拟盘
```
