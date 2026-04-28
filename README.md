<div align="center">

# QuantGPT

**Automated Alpha Signal Factory — From Natural Language to BRAIN-Ready Factors in 2 Minutes**

自然语言描述 → AI 因子设计 → 全市场回测 → 多维评分 → WorldQuant BRAIN 直接验证 | 370+ 回测任务实战验证

[![CI](https://github.com/Miasyster/quantgpt/actions/workflows/ci.yml/badge.svg)](https://github.com/Miasyster/quantgpt/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React_18-TypeScript-61DAFB?logo=react&logoColor=white)](https://react.dev)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Quick Start](docs/QUICKSTART.md) ·
[Architecture](docs/ARCHITECTURE.md) ·
[API Docs](docs/API_DOC.md) ·
[MCP Guide](docs/MCP_GUIDE.md) ·
[Factor Mining](docs/FACTOR_MINING.md) ·
[Contributing](CONTRIBUTING.md)

</div>

---

## Why This Project Matters

QuantGPT is the factor research engine extracted from a production multi-factor research infrastructure, focused on the most time-consuming part of quant research: **factor discovery and validation**.

传统因子研究的"构思→编码→回测→评估"流程通常需要数小时。QuantGPT 将其压缩到 **2 分钟以内**：

```
"找一个基于价量背离的短期反转因子"
```

一句自然语言输入，系统自动完成：LLM 因子设计 → 表达式生成 → A 股全市场回测 → 多维度评分 → 反过拟合检测 → HTML 报告输出。全程零代码、零人工干预。

### Production Track Record

| Metric | Value |
|:-------|:------|
| 累计回测任务 | **370+** |
| 单轮迭代（8 候选因子） | **~15 分钟** |
| 自然语言 → 完整报告 | **< 2 分钟** |
| 表达式算子标准 | **WorldQuant BRAIN 对齐** |
| BRAIN 正式提交 | **Fitness 1.07, IS 全部 PASS, 已提交** |
| WQ BRAIN 集成 | **内置 API — 一键模拟 + 自动提交** |

所有因子表达式采用 WorldQuant BRAIN 算子标准。QuantGPT 已内置 WQ BRAIN API 集成，**从因子设计到 BRAIN 正式提交全程自动化**，无需手动登录平台。首个因子已通过全部 IS 检测并正式提交（alpha_id: `78aAQjoL`）。

---

## Validated Results — First Factor Officially Submitted to BRAIN

经过系统化参数优化（9 个变体网格搜索），首个因子已**通过 WQ BRAIN 全部 IS 检测并正式提交**：

| Factor | Expression | WQ Sharpe | WQ Fitness | IS Tests | Status |
|:-------|:-----------|:---------:|:----------:|:--------:|:------:|
| **VWAP Decay Reversal (10d)** | `-1 * rank(ts_decay_linear(close / vwap, 10))` | **1.69** | **1.07** | **ALL PASS** | **Submitted** |
| Price-Volume Divergence (5d) | `-1 * rank(ts_corr(close, volume, 5))` | 1.73 | 0.60 | 6/7 PASS | Validated |
| Dual Divergence Composite | `rank(-1*ts_corr(close,volume,5))*rank(-1*ts_corr(high,volume,10))` | 1.20 | 0.41 | 6/7 PASS | Validated |

> **VWAP Decay Reversal** 是 QuantGPT 首个正式提交 BRAIN 的因子（alpha_id: `78aAQjoL`）。突破关键：将中性化从 SUBINDUSTRY 切到 MARKET，Fitness 从 0.88 → 1.07，Returns 从 14.51% → 18.63%。全程通过 QuantGPT 内置 WQ BRAIN API 完成，无需手动登录平台。

<p align="center">
  <img src="example_factor/4-1.png" width="49%" alt="WQ BRAIN PnL — VWAP Decay Reversal (Submitted)" />
  <img src="example_factor/4-2.png" width="49%" alt="WQ BRAIN IS Summary — VWAP Decay Reversal (Submitted)" />
</p>
<p align="center">
  <sub>VWAP Decay Reversal — 已正式提交：Sharpe 1.69, Fitness 1.07, IS 全部 PASS，逐年 Sharpe 全正（2019: 2.35, 2020: 3.43, 2021: 1.95, 2022: 0.83, 2023: 1.26）</sub>
</p>

<p align="center">
  <img src="example_factor/2-1.png" width="49%" alt="WQ BRAIN PnL — Price-Volume Divergence" />
  <img src="example_factor/2-2.png" width="49%" alt="WQ BRAIN IS Testing — Price-Volume Divergence" />
</p>
<p align="center">
  <sub>Price-Volume Divergence：Sharpe 1.73，IS 6/7 PASS</sub>
</p>

<p align="center">
  <img src="example_factor/3-1.png" width="49%" alt="WQ BRAIN PnL — Dual Divergence Composite" />
  <img src="example_factor/3-2.png" width="49%" alt="WQ BRAIN IS Testing — Dual Divergence Composite" />
</p>
<p align="center">
  <sub>Dual Divergence Composite：Sharpe 1.20，IS 6/7 PASS</sub>
</p>

---

## AI Factor Mining — Autonomous Research Loop

> **This is what makes QuantGPT fundamentally different from every other quant tool.**
>
> 传统工具给你一个回测引擎，然后说"去写因子吧"。QuantGPT 给你一个**自主研究员**——它读文献、设计假设、批量实验、分析结果、积累知识、自我迭代，而且每个结论都经过双模型交叉验证。

### How It Works

```
                    ┌─────────────────────────────┐
                    │  Research Notes & Knowledge  │
                    │  (Rules / Findings / Fails)  │
                    └──────────┬──────────────────┘
                               │ read
                               ▼
┌──────────┐    ┌──────────────────────────┐    ┌──────────────────┐
│  Phase 0 │───▶│  Phase 1: Factor Design  │───▶│  Phase 2: Batch  │
│  Context │    │  Hypothesis → Expression │    │  Backtest (10-20 │
│  Loading │    │  1-3 candidates per idea │    │  concurrent)     │
└──────────┘    └──────────────────────────┘    └────────┬─────────┘
                                                         │
                               ┌─────────────────────────┘
                               ▼
                ┌──────────────────────────────────────────┐
                │  Phase 3: Four-Step Analysis             │
                │                                          │
                │  ① Fact Collection (metrics vs baseline) │
                │  ② Independent Judgment (Agent)          │
                │  ③ Cross-Review (DeepSeek Reasoner)      │
                │  ④ Consensus or Divergence Resolution    │
                └──────────────────┬───────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
          ┌─────────────────┐          ┌──────────────────┐
          │  Phase 4: Update │          │  Phase 5: Stop?  │
          │  Notes + Knowledge│         │  Converged /     │
          │  Base             │◀────────│  Time / Rounds   │
          └─────────────────┘          └──────────────────┘
                    │                         │ no
                    │                         └──▶ back to Phase 1
                    ▼
          ┌──────────────────┐
          │  Phase 6: Report │
          │  A/B factors +   │
          │  new knowledge   │
          └──────────────────┘
```

### Why This Matters — Competitive Comparison

| Capability | Manual Research | ChatGPT + Backtest | **QuantGPT Factor Mining** |
|:-----------|:--------------:|:------------------:|:--------------------------:|
| Factor design | Human | Single LLM, one-shot | **LLM + knowledge base + hypothesis-driven** |
| Experiment scale | 1-3 per hour | 1-3 per session | **10-20 concurrent per batch** |
| Anti-bias | Researcher's judgment | None | **Dual-LLM cross-review (mandatory)** |
| Knowledge accumulation | Personal notes | Lost between sessions | **Structured KB: rules / findings / failures** |
| Checkpoint & resume | Manual | Start over | **Auto-detect unfinished directions** |
| Research discipline | Varies by person | None enforced | **Control variables, no repeats, record failures** |
| Convergence detection | Intuition | None | **Auto-stop after N rounds without improvement** |

### Key Mechanisms

<table>
<tr>
<td width="50%">

**Dual-LLM Cross-Review**

每个结论性判断（采用/不采用/关闭方向）必须经过第二个 LLM 独立评审。不是简单的"再问一遍"——是把事实数据和第一个模型的推理链一起发给 DeepSeek Reasoner，要求它独立评估推理是否合理、是否有遗漏角度。

共识 → 直接输出。分歧 → 呈现双方证据，采用更保守结论。

这解决了单模型因子研究的核心问题：**confirmation bias**。

</td>
<td width="50%">

**Persistent Knowledge Base**

```
research_notes/knowledge/
├── rules/       ← 已验证的稳定规则（必须遵守）
├── findings/    ← 经验发现（参考）
└── failures/    ← 已证伪路径（禁止重复）
```

知识库跨会话积累。第 10 次研究会话可以直接利用前 9 次的所有发现，避免重复实验，遵守已验证规则，绕开已证伪路径。

这不是 chat history——是**结构化的研究资产**。

</td>
</tr>
<tr>
<td>

**Batch Concurrent Evaluation**

单次提交 10-20 个因子表达式，并发回测 + 三波重试。结果按 fitness 降序排列。hs300 fitness < 0.1 时自动跳过 csi500 验证，节省算力。

```python
from scripts.factor_miner import batch_evaluate
results = batch_evaluate(
    server, expressions, params,
    max_concurrent=10
)
```

</td>
<td>

**Research Discipline (Enforced)**

不是建议，是硬性规则：
- 每次实验只改一个变量
- 提交前检查是否已做过（笔记 + 知识库）
- 分析结论标注"仅为假设"
- 失败实验同样记录原因
- 表达式 > 4 层嵌套需额外论证
- 简单清晰 > 复杂精巧

</td>
</tr>
</table>

> **上面 Validated Results 中的因子就是这个流程的产出。** 3 轮迭代、24 个候选、最终 3 个因子通过 WQ BRAIN 独立验证。完整方法论见 [Factor Mining Guide](docs/FACTOR_MINING.md)。

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        QuantGPT Platform                        │
├──────────┬──────────────────────────────┬───────────────────────┤
│          │          Core Engine         │                       │
│  Client  │  ┌──────────────────────┐   │   Data Layer          │
│  Layer   │  │  Expression Parser   │   │  ┌─────────────────┐  │
│          │  │  50+ operators       │   │  │ baostock (free)  │  │
│ Web SPA  │  │  WQ BRAIN compatible │   │  │ akshare (free)   │  │
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
│          │  Factor Iteration Engine    │  │ SQLite (default)│  │
│          │  Trajectory → Meta-Evo →    │  │ PostgreSQL (opt)│  │
│          │  Mutation / Crossover       │  └─────────────────┘  │
├──────────┴──────────────────────────────┴───────────────────────┤
│  Deploy: Alibaba Cloud ECS · Nginx · Cloudflare · systemd      │
└─────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|:------|:-----------|
| Backend | Python 3.10+, FastAPI, uvicorn, SQLAlchemy 2.0 async |
| Database | SQLite (default, zero-config) / PostgreSQL (optional) |
| AI/LLM | DeepSeek (optional — expression-only mode works without LLM) |
| Market Data | baostock + akshare (free) → Parquet cache → rqdatac (optional) |
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
| **WQ BRAIN API** | `wq_brain_client.py` | **直连 BRAIN 平台 — 真实模拟 + IS 检测 + 一键正式提交** |

### 3. Evolutionary Factor Iteration

受 QuantaAlpha 启发的三阶段自动搜索：

```
TrajectoryAnalyzer → MetaEvolutionSelector → Strategy Execution
 (质量指标评估)       (EXPLOIT/EXPLORE/        (MutationEngine ×8 方向
                      RECOMBINE/SIMPLIFY)       / CrossoverEngine)
```

8 种定向突变：时间窗口变异、算子替换、复杂度调整、截面变换叠加等。5 维评分驱动迭代方向。

### 4. Free Data Sources with Graceful Degradation

```
Parquet local cache (zero network, CACHE_ONLY mode for offline)
    ↓ cache miss?
baostock (free, no account needed, T+1 data)
    ↓ need same-day data?
akshare (free, same-day data from 东方财富)
    ↓ need batch API?
rqdatac (optional, paid, professional batch API)
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
# Clone & one-click setup (no Docker, no API keys needed)
git clone https://github.com/Miasyster/QuantGPT.git && cd QuantGPT
make setup   # creates venv, installs deps, generates .env
make run     # starts server at http://localhost:8002
```

Open `http://localhost:8002` and enter a factor expression:

```
rank(close / ts_mean(close, 20))
```

**Zero config by default**: SQLite database, baostock + akshare free data, no LLM required for expression mode. See [full Quick Start guide](docs/QUICKSTART.md) for details.

<details>
<summary><b>Optional: Enable natural language mode</b></summary>

```bash
# Edit .env, add your DeepSeek API key (~$0.001 per query)
DEEPSEEK_API_KEY=sk-your-key-here
```

Then you can type: *"找一个基于价量背离的短期反转因子"*

</details>

<details>
<summary><b>Optional: PostgreSQL (for production)</b></summary>

```bash
pip install "quantgpt[postgresql]"
# Edit .env:
DATABASE_URL=postgresql+asyncpg://quantgpt:password@localhost:5432/quantgpt
alembic upgrade head
```

</details>

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
# VWAP decay reversal — BRAIN submitted, Fitness 1.07, IS ALL PASS
-1 * rank(ts_decay_linear(close / vwap, 10))

# Price-volume divergence — BRAIN Sharpe 1.73
-1 * rank(ts_corr(close, volume, 5))

# 20-day momentum
rank(close / ts_mean(close, 20))

# Low volatility
rank(-1 * ts_std(close/ts_shift(close,1)-1, 20))

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
| Autonomous factor mining | -- | -- | -- | **6-phase research loop** |
| Dual-LLM cross-review | -- | -- | -- | **Mandatory** |
| Knowledge accumulation | -- | -- | -- | **Structured KB** |
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

[MIT](LICENSE) — Copyright (c) 2026 Miasyster

This repository is the **original source** of the QuantGPT factor research engine.
Derivative works should retain the copyright notice and comply with the MIT License terms.
See [NOTICE](NOTICE) for details.

<sub>*Past factor performance does not guarantee future returns. This project does not constitute investment advice.*</sub>
