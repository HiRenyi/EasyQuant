<div align="center">

# QuantGPT

**AI-Driven Alpha Factor Research Engine for A-Share Market**

用一句中文描述因子逻辑 → 自动生成表达式 → 执行分组回测 → 输出可直接提交 WorldQuant BRAIN 的 alpha 因子

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React_18-TypeScript-61DAFB?logo=react&logoColor=white)](https://react.dev)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Live Demo](https://quantgpt.online) ·
[API Docs](docs/API_DOC.md) ·
[MCP Guide](docs/MCP_GUIDE.md)

</div>

---

## Why This Project Matters

大多数量化回测工具要求用户写 Python 代码。QuantGPT 将整个因子研究流程压缩为一句自然语言：

```
"找一个基于价量背离的短期反转因子"
```

系统自动完成：LLM 因子设计 → 表达式生成 → A 股分组回测 → 反过拟合检测 → 评分评级 → HTML 报告。产出的因子表达式与 WorldQuant BRAIN 算子标准对齐，可直接复制到 BRAIN 平台做独立验证。

---

## Validated Results

3 轮迭代、24 个候选表达式，产出以下因子并在 **WorldQuant BRAIN（美股 TOP3000）** 上完成独立验证：

| Factor | Expression | A-Share Sharpe | US Sharpe | BRAIN IS Tests |
|:-------|:-----------|:--------------:|:---------:|:--------------:|
| Price-Volume Divergence (5d) | `-1 * rank(ts_corr(close, volume, 5))` | 1.42 | **1.73** | **6/7 PASS** |
| Price-Volume Divergence (10d) | `-1 * rank(ts_corr(close, volume, 10))` | 0.66 | 0.91 | 4/7 PASS |
| Dual Divergence Composite | `rank(-1*ts_corr(close,volume,5))*rank(-1*ts_corr(high,volume,10))` | 0.87 | **1.20** | **6/7 PASS** |

> 三个因子在 A 股和美股两个完全独立的市场、完全独立的回测引擎上均表现有效。

<p align="center">
  <img src="example_factor/2-1.png" width="49%" alt="WQ BRAIN PnL — Factor 1" />
  <img src="example_factor/2-2.png" width="49%" alt="WQ BRAIN IS Testing — Factor 1" />
</p>
<p align="center">
  <sub>WorldQuant BRAIN 独立验证：Factor 1 PnL 曲线（Sharpe 1.73）+ IS Testing Summary（6/7 PASS）</sub>
</p>

<p align="center">
  <img src="example_factor/3-1.png" width="49%" alt="WQ BRAIN PnL — Factor 3" />
  <img src="example_factor/3-2.png" width="49%" alt="WQ BRAIN IS Testing — Factor 3" />
</p>
<p align="center">
  <sub>Factor 3 Dual Divergence Composite：Sharpe 1.20，6/7 PASS</sub>
</p>

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        QuantGPT Platform                        │
├──────────┬──────────────────────────────┬───────────────────────┤
│          │          Core Engine         │                       │
│  Client  │  ┌──────────────────────┐   │   Data Layer          │
│  Layer   │  │  Expression Parser   │   │  ┌─────────────────┐  │
│          │  │  50+ operators       │   │  │ rqdatac (primary)│  │
│ Web SPA  │  │  WQ BRAIN compatible │   │  │ baostock (free)  │  │
│ REST API │  └──────────┬───────────┘   │  │ Parquet cache    │  │
│ MCP      │  ┌──────────▼───────────┐   │  └─────────────────┘  │
│          │  │  Backtest Engine     │   │                       │
│          │  │  Rank-based grouping │   │   AI Layer            │
│          │  │  WQ BRAIN aligned    │   │  ┌─────────────────┐  │
│          │  └──────────┬───────────┘   │  │ DeepSeek LLM    │  │
│          │  ┌──────────▼───────────┐   │  │ Factor design   │  │
│          │  │  Validation Suite    │   │  │ Iteration       │  │
│          │  │  Anti-overfit (4x)   │   │  │ Mutation engine │  │
│          │  │  Walk-forward        │   │  └─────────────────┘  │
│          │  │  WQ BRAIN simulation │   │                       │
│          │  └──────────────────────┘   │   Storage             │
│          │                             │  ┌─────────────────┐  │
│          │  Factor Iteration Engine    │  │ PostgreSQL      │  │
│          │  Trajectory → Meta-Evo →    │  │ Alembic (11 ver)│  │
│          │  Mutation / Crossover       │  └─────────────────┘  │
├──────────┴──────────────────────────────┴───────────────────────┤
│  Deploy: Alibaba Cloud ECS · Nginx · Cloudflare · systemd      │
└─────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|:------|:-----------|
| Backend | Python 3.10+, FastAPI, uvicorn, SQLAlchemy 2.0 async |
| Database | PostgreSQL + asyncpg + Alembic migrations |
| AI/LLM | DeepSeek (OpenAI-compatible API, swappable) |
| Market Data | rqdatac (primary) → baostock (free fallback) → Parquet cache |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS 4 |
| Auth | JWT (access + refresh) + email verification + bcrypt |
| MCP | FastMCP (stdio / SSE / streamable-http) |
| Report | QuantStats HTML |
| Deploy | Alibaba Cloud ECS, Nginx, Cloudflare, systemd |

---

## Key Engineering Decisions

### 1. Expression Parser — The Core Differentiator

自研的表达式解析器（`expression_parser.py`, 870+ lines）是整个系统的核心：

- **50+ 算子**：截面（`rank`, `zscore`）、时序（`ts_corr`, `decay_linear`）、非线性（`sign_power`）、条件（`where`, `trade_when`）、技术指标（`rsi`, `macd`, `atr`）
- **双模式**：`mode="wq"` 仅允许 WQ BRAIN 兼容算子（提交前校验），`mode="local"` 开放全部算子
- **语义正确的截面/时序分离**：`rank()` 按 `trade_date` 分组（截面），`ts_mean()` 按 `stock_code` 分组（时序），自动处理分组逻辑
- **安全约束**：递归深度限制、窗口上限、表达式长度限制，防止恶意输入

### 2. Three-Layer Anti-Overfit System

| Layer | Module | Method |
|:------|:-------|:-------|
| Statistical Tests | `anti_overfit.py` | IC 稳定性 + 子样本压力测试（牛/熊/震荡）+ 安慰剂检验 + 半衰期估计 |
| Walk-Forward | `rolling_validator.py` | 滚动 train/valid/test 窗口，评估样本外 IC 衰减 |
| WQ Simulation | `wq_simulate.py` | Dollar-neutral 多空模拟，对齐 BRAIN 的 Sharpe/Turnover/Fitness 计算 |

### 3. Evolutionary Factor Iteration

受 QuantaAlpha 启发的三阶段自动搜索：

```
TrajectoryAnalyzer → MetaEvolutionSelector → Strategy Execution
 (质量指标评估)       (EXPLOIT/EXPLORE/        (MutationEngine ×8 方向
                      RECOMBINE/SIMPLIFY)       / CrossoverEngine)
```

8 种定向突变：时间窗口变异、算子替换、复杂度调整、截面变换叠加等。5 维评分驱动迭代方向。

### 4. Triple Data Source with Graceful Degradation

```
rqdatac (professional, batch API)
    ↓ unavailable?
baostock (free, single-stock, thread-safe with global lock)
    ↓ already cached?
Parquet local cache (zero network, CACHE_ONLY mode for offline)
```

### 5. Three Access Modes

| Mode | Use Case |
|:-----|:---------|
| **Web SPA** | 自然语言输入 + SSE 实时进度 + 交互式报告 |
| **REST API** | 程序化批量回测、与外部系统集成 |
| **MCP** | Claude Code / Claude Desktop 原生调用，AI Agent 直接具备因子研究能力 |

<details>
<summary><b>MCP Tools (8 个)</b></summary>

| Tool | Description |
|:-----|:------------|
| `list_operators` | 全部算子文档 |
| `list_universes` | 股票池和基准 |
| `validate_expression` | 语法校验 |
| `run_backtest` | 完整回测 |
| `score_factor` | 评分（0–100, A/B/C/D） |
| `diagnose_factor` | 失败模式诊断 + 改进建议 |
| `run_anti_overfit` | 4 项反过拟合检验 |
| `run_rolling_validation` | Walk-forward 验证 |

</details>

---

## Product Features

<table>
<tr>
<td width="50%">

**Factor Backtesting**
- 自然语言 / 表达式双入口
- SSE 实时进度推送
- IC/IR、多空夏普、换手率、单调性
- 交易成本扣除
- QuantStats HTML 完整报告

</td>
<td width="50%">

**Factor Iteration**
- LLM 驱动的自动化因子搜索
- 8 种变异方向 + 交叉引擎
- 元演化策略自适应选择
- 5 维评分体系
- 轨迹分析防止无效迭代

</td>
</tr>
<tr>
<td>

**Validation & Risk Control**
- 4 项反过拟合统计检验
- Walk-forward 滚动验证
- WQ BRAIN dollar-neutral 模拟
- 行业 + 市值中性化
- 自动因子方向检测

</td>
<td>

**Platform Capabilities**
- 因子库收藏与管理
- 多因子合成（等权 / IC 加权）
- 因子对比（相关性矩阵）
- 每日量化日报（LLM 生成）
- 模拟盘（每日自动结算）
- 策略回测（聚宽平台对接）

</td>
</tr>
</table>

---

## Quick Start

```bash
# Clone & install
git clone https://github.com/Miasyster/QuantGPT.git && cd QuantGPT
pip install -e .

# Configure (minimum 3 env vars)
cp .env.example .env
# Edit: DEEPSEEK_API_KEY, DATABASE_URL, JWT_SECRET_KEY

# Database
docker run -d --name quantgpt-pg \
  -e POSTGRES_USER=quantgpt -e POSTGRES_PASSWORD=password -e POSTGRES_DB=quantgpt \
  -p 5432:5432 postgres:16-alpine
alembic upgrade head

# Build & run
cd frontend && npm install && npm run build && cd ..
python -m quantgpt --transport http --port 8002
# → http://localhost:8002
```

<details>
<summary><b>MCP Configuration (Claude Code / Claude Desktop)</b></summary>

```json
{
  "mcpServers": {
    "quantgpt": {
      "command": "python",
      "args": ["-m", "quantgpt"]
    }
  }
}
```

Then in Claude: *"帮我在中证500上测试一个低波动率因子"*

</details>

<details>
<summary><b>REST API Quick Example</b></summary>

```bash
# Submit backtest
curl -X POST http://localhost:8002/api/v1/auto_backtest \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "20日动量因子", "universe": "hs300"}'

# Stream results (SSE)
curl "http://localhost:8002/api/v1/tasks/{task_id}/stream?token=<token>"
```

</details>

<details>
<summary><b>Expression Examples</b></summary>

```python
# 20-day momentum
rank(close / ts_mean(close, 20))

# Price-volume divergence (BRAIN validated, Sharpe 1.73)
-1 * rank(ts_corr(close, volume, 5))

# Low volatility
rank(-1 * ts_std(close/ts_shift(close,1)-1, 20))

# RSI oversold signal
where(rsi(close, 14) < 30, 1, 0)

# Decay-weighted correlation
decay_linear(rank(ts_corr(vwap, volume, 10)), 5)
```

</details>

---

## Project Structure

```
quantgpt/
├── quantgpt/                    # Backend (Python)
│   ├── expression_parser.py     # Factor expression parser (50+ ops, WQ compatible)
│   ├── backtest.py              # Rank-based group backtest engine
│   ├── market_data.py           # rqdatac → baostock → Parquet cache
│   ├── api_server.py            # FastAPI REST API + SSE
│   ├── mcp_server.py            # FastMCP server (8 tools)
│   ├── iteration.py             # 3-phase evolutionary iteration
│   ├── mutation_engine.py       # 8 directed mutation strategies
│   ├── anti_overfit.py          # 4 statistical anti-overfit tests
│   ├── rolling_validator.py     # Walk-forward validation
│   ├── wq_simulate.py           # WQ BRAIN dollar-neutral simulator
│   ├── neutralize.py            # Industry & cap neutralization
│   ├── paper_engine.py          # Paper trading engine
│   ├── daily_summary.py         # LLM-powered daily market report
│   └── routes/                  # 10 API route modules
├── frontend/                    # React 18 + TypeScript + Tailwind CSS 4
│   └── src/components/          # 40+ components
├── tests/                       # 74 tests (parser + backtest + WQ simulate)
├── example_factor/              # BRAIN validation screenshots
└── deploy/                      # Production deploy scripts
```

---

## Competitive Landscape

| Capability | JoinQuant | Backtrader | vnpy | **QuantGPT** |
|:-----------|:------:|:------:|:------:|:------:|
| Input method | Write Python | Write Python | Write Python | **Natural language** |
| Factor backtesting | Manual | Manual | N/A | **One-click** |
| AI factor generation | -- | -- | -- | **LLM-driven** |
| Anti-overfit detection | -- | -- | -- | **4 statistical tests** |
| WQ BRAIN compatible | -- | -- | -- | **Operator-aligned** |
| MCP / AI Agent | -- | -- | -- | **8 tools** |
| Live trading | Yes | Limited | Yes | -- |
| Intraday data | Yes | Yes | Yes | Daily only |

---

## Limitations

- **Daily frequency only** — no intraday backtesting
- **Monolithic architecture** — in-memory task queue, single-instance
- **Strategy backtesting requires JoinQuant account** (optional feature)

---

## License

[MIT](LICENSE)

<sub>*Past factor performance does not guarantee future returns. This project does not constitute investment advice.*</sub>
