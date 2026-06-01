<div align="center">

# EasyQuant

**Agent-Driven LLM Quant Research + JoinQuant Auto-Backtest Platform**

Forked from [Miasyster/QuantGPT](https://github.com/Miasyster/QuantGPT) — 扩展聚宽 (JoinQuant) 自动回测、批量策略提交、策略验证与文档。感谢原作者的优秀基础。

LLM Agent 自治因子挖矿 → 聚宽 Playwright 自动回测 → 批量策略提交 → 策略验证库 | 全程零人工干预

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Playwright](https://img.shields.io/badge/Playwright-Automation-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Quick Start](#quick-start) ·
[Architecture](#architecture) ·
[Validated Strategies](validated-strategies/README.md) ·
[API Docs](docs/API_DOC.md) ·
[MCP Guide](docs/MCP_GUIDE.md) ·
[Factor Mining](docs/FACTOR_MINING.md)

</div>

---

## What Is EasyQuant

本项目基于 [Miasyster/QuantGPT](https://github.com/Miasyster/QuantGPT)（Agent 驱动的 LLM 量化因子研究引擎），在此基础上增加了以下扩展能力：

1. **聚宽 (JoinQuant) 自动回测** — Playwright 浏览器自动化，直接在聚宽网页端运行回测，支持登录、代码注入、结果抓取
2. **批量策略提交** — 自动按代码长度排序、逐个提交、等待完成、记录回测指标到 `回测结果.md`
3. **策略验证库** — 28 个验证通过的策略源代码 + 指标文档，中文命名存放在 `validated-strategies/`
4. **单任务串行执行** — 适配聚宽非 VIP 账号限制（仅支持 1 个回测任务同时进行）

### 原始项目说明（来自 QuantGPT）

QuantGPT 是一个 **Agent 驱动的因子研究引擎**。Agent（Claude，通过 MCP）自主发现、评估、迭代 alpha 因子表达式，最终可提交到 WorldQuant BRAIN。

核心架构：

```
LLM Agent (Claude Code / Claude Desktop)
    │
    ├── MCP Tools (8 个)          ← Agent 的工具箱
    │   ├── run_backtest           ← 全市场分组回测
    │   ├── score_factor           ← 0-100 综合评分
    │   ├── diagnose_factor        ← 失败模式诊断
    │   ├── run_anti_overfit       ← 4 项反过拟合检验
    │   ├── run_rolling_validation ← Walk-forward 验证
    │   ├── validate_expression    ← 语法校验
    │   ├── list_operators         ← 50+ 算子文档
    │   └── list_universes         ← 股票池和基准
    │
    ├── WQ BRAIN Integration       ← WorldQuant 直连
    │   ├── Dollar-neutral 模拟
    │   ├── IS 检测对齐
    │   └── 一键正式提交
    │
    └── JoinQuant Integration      ← 聚宽自动回测（EasyQuant 扩展）
        ├── JQAutomationService    ← Playwright 浏览器自动化
        ├── StrategyBacktest API   ← 策略代码上传 → 聚宽回测 → 结果抓取
        ├── Batch Submission       ← 批量提交脚本
        └── Validated Strategies   ← 28 个已验证策略库
```

### 生产记录

| 指标 | 数值 |
|:------|:------|
| 累计回测任务 | **370+** |
| 聚宽策略回测 | **55+ 个策略**（2025 年精选） |
| WQ BRAIN 正式提交 | **3 个因子 IS 全部 PASS，已提交（最佳 Fitness 1.26）** |
| 单轮迭代（8 候选因子） | **~15 分钟** |

---

## Validated Results — JoinQuant Strategies

聚宽回测已完成 **28 个验证策略**（2025-01-01 ~ 2025-12-31，初始资金 100 万），详见 [validated-strategies/README.md](validated-strategies/README.md)。

**注意**：`validated-strategies/code/` 中的代码为实际通过回测的修改版本（已去除原始聚宽注释），非原始聚宽文章克隆代码。

| # | 策略 | 年化收益 | 最大回撤 | 夏普比率 |
|:--|------|:--------:|:--------:|:--------:|
| 1 | [首板高开-低开-弱转强](validated-strategies/first-board-mixed-strategy.md) | **158.72%** | 43.97% | **2.62** |
| 2 | [子账户多策略分仓](validated-strategies/sub-account-multi-strategy.md) | **81.77%** | 18.26% | **2.43** |
| 3 | [小市值排除3bug版](validated-strategies/small-cap-exclude-bugs.md) | **81.77%** | 18.26% | **2.43** |
| 4 | [基本面01+RSI择时](validated-strategies/fundamental-rsi-timing.md) | **64.30%** | 14.75% | **2.41** |
| 5 | [干积分-量化框架](validated-strategies/earnings-points-framework.md) | **60.04%** | 23.29% | **2.33** |
| 6 | [稳健型ETF](validated-strategies/stable-etf-strategy.md) | **22.16%** | **3.08%** | **2.29** |
| 7 | [国九小市值](validated-strategies/guojiu-small-cap.md) | **74.84%** | 21.23% | **2.21** |
| 8 | [高股息价投](validated-strategies/dividend-value-strategy.md) | **51.50%** | 16.65% | **2.17** |
| 9 | [四大搅屎棍](validated-strategies/four-stirrers-strategy.md) | **58.68%** | 18.78% | **1.93** |
| 10 | [趋势筛选ETF轮动](validated-strategies/trend-filter-etf-rotation.md) | **41.50%** | 12.52% | **1.83** |

完整 28 个策略列表和代码见 [validated-strategies/](validated-strategies/)。

---

## WQ BRAIN Factors Submitted

原始 QuantGPT 项目产出的 3 个正式提交因子，全部通过 WQ BRAIN IS 检测：

| Factor | Expression | WQ Sharpe | WQ Fitness | WQ Returns | IS Tests | Status |
|:-------|:-----------|:---------:|:----------:|:----------:|:--------:|:------:|
| **Debt-Momentum** | `-1 * rank(ts_av_diff(close, 10)) + rank(debt / enterprise_value)` | **1.77** | **1.26** | **20.18%** | **ALL PASS** | **Submitted** |
| **VWAP Decay** | `-1 * rank(ts_decay_linear(close / vwap, 10))` | **1.69** | **1.07** | **18.63%** | **ALL PASS** | **Submitted** |
| **Returns-Volume** | `-1 * rank(ts_decay_linear(returns * volume / adv20, 5))` | **1.60** | **1.03** | **24.15%** | **ALL PASS** | **Submitted** |

---

## How It Works

### Part 1: Agent Factor Mining (from QuantGPT)

Agent 自主设计因子表达式 → 本地回测 → 评分 → 反过拟合 → 迭代优化 → WQ BRAIN 提交。

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
                    ┌────────────────────────────────────┘
                    ▼
          ┌──────────────────────────────────┐
          │  Phase 3: Analysis & Review      │
          │  Fact Collection + Dual-LLM      │
          └────────────────┬─────────────────┘
                           ▼
              ┌────────────┴────────────┐
              │  Update KB or Stop?     │
              └────────────┬────────────┘
                           │
              Converged? ──┼─ yes → Report
                           │
              no ──────────┴─ back to Phase 1
```

关键机制：
- **双 LLM 交叉评审** — 每个结论经第二个模型独立验证，消除 confirmation bias
- **持久化知识库** — `research_notes/knowledge/` 跨会话积累，避免重复实验
- **批量并发评估** — 单次 10-20 个因子，并发回测 + 三波重试

### Part 2: JoinQuant Auto-Backtest (EasyQuant Extension)

针对聚宽平台的自动化回测流程：

```
用户/脚本
    │
    ▼
┌──────────────────────────────────────┐
│  submit_next.py                      │
│  1. 读取回测结果.md，获取已处理策略    │
│  2. 按代码长度排序（短的优先）         │
│  3. 提取策略代码                     │
│  4. 调用 API 提交                    │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  strategy_backtest API               │
│  1. AST 验证策略代码                 │
│  2. Playwright 登录聚宽              │
│  3. 注入代码 + 设置回测参数          │
│  4. 点击运行 + 等待完成              │
│  5. 抓取回测指标                     │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  JQAutomationService                 │
│  Playwright 浏览器自动化              │
│  - 登录 + 会话保持                    │
│  - 负积分检测                         │
│  - 超时 + 重试                        │
│  - 结果抓取                           │
└──────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+（前端）
- Playwright（聚宽自动化，`pip install playwright && playwright install chromium`）
- DeepSeek API Key（可选，用于 Agent 因子挖掘）
- 聚宽账号（免费，非 VIP 仅支持 1 个回测任务同时进行）

### Option 1: Agent Mode — Factor Mining

```bash
git clone https://github.com/HiRenyi/EasyQuant.git && cd EasyQuant
make setup   # 创建虚拟环境、安装依赖、生成 .env
make run     # 启动服务 http://localhost:8003
```

配置 MCP（Claude Code 或 Claude Desktop）：

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

然后让 Agent 自主工作：*"在沪深300上挖掘高 fitness 的因子，目标 WQ BRAIN 可提交"*

### Option 2: JoinQuant Auto-Backtest — Batch Strategy Submission

**第一步：保存聚宽登录凭证**

```bash
python scripts/save_jq_login.py
# 按提示输入聚宽账号密码，会保存到 .env
```

**第二步：启动服务**

```bash
./restart.sh
# 或手动启动：
PYTHONUNBUFFERED=1 python -m quantgpt
```

**第三步：批量提交策略**

```bash
# 将策略 .txt/.py 文件放到 strategy-collection/ 目录
python scripts/submit_next.py
```

脚本会自动：
1. 读取 `回测结果.md`，跳过已处理的策略
2. 按代码长度排序（短的优先，节省积分）
3. 逐个提交，等待完成，记录结果
4. 处理各种错误（验证失败、积分不足、超时等）

**第四步：查看结果**

```bash
cat 回测结果.md
# 或打开 validated-strategies/ 查看已验证策略
```

### Option 3: Direct API — Single Strategy Backtest

```bash
# 直接通过 API 提交单个聚宽策略
curl -X POST http://localhost:8003/api/v1/strategy-backtest \
  -H "Content-Type: application/json" \
  -d '{
    "strategyName": "我的策略",
    "code": "from jqdata import *\n\ndef initialize(context):\n    ...",
    "start_date": "2025-01-01",
    "end_date": "2025-12-31"
  }'

# 查询任务状态
curl http://localhost:8003/api/v1/tasks/<task_id>
```

### Option 4: Expression Mode — Local Factor Backtest

```bash
# 本地表达式回测（无需聚宽）
curl -X POST http://localhost:8003/api/v1/auto_backtest \
  -H "Content-Type: application/json" \
  -d '{"expression": "rank(close / ts_mean(close, 20))", "universe": "hs300"}'
```

---

## Project Structure

```
EasyQuant/
├── quantgpt/                    # 后端（QuantGPT + EasyQuant 扩展）
│   ├── expression_parser.py     # 因子表达式解析器（50+ 算子）
│   ├── backtest.py              # 本地排名回测引擎
│   ├── jq_automation.py         # ★ 聚宽 Playwright 浏览器自动化
│   ├── task_store.py            # 任务持久化 + 状态管理
│   ├── strategy_code_utils.py   # 策略代码 AST 验证
│   ├── llm_service.py           # LLM 集成服务
│   ├── routes/
│   │   ├── strategy_backtest.py # ★ 聚宽策略回测 API
│   │   └── backtest_tasks.py    # ★ 任务管理
│   └── ...                      # 原始 QuantGPT 模块
├── validated-strategies/        # ★ 28 个已验证策略（EasyQuant）
│   ├── README.md                # 策略指标索引
│   ├── code/                    # 策略源代码（28 个，实际回测修改版，中文命名）
│   └── *.md                     # 详细分析文档（Top 10）
├── scripts/
│   ├── factor_miner.py          # 批量因子挖掘（来自 QuantGPT）
│   ├── submit_next.py           # ★ 批量策略提交脚本
│   ├── save_jq_login.py         # ★ 保存聚宽登录凭证
│   └── batch_backtest.py        # ★ 批量回测辅助脚本
├── strategy-collection/          # ★ 策略收集（运行时，未验证的不入 git）
│   └── validated/                #   已验证策略（28 个，中文命名，git 跟踪）
├── 回测结果.md                   # ★ 批量回测结果日志（运行时）
├── restart.sh                   # 服务重启脚本
├── frontend/                    # React 监控面板
├── docs/                        # 文档
└── tests/                       # 74 个测试
```

---

## Tech Stack

| Layer | Technology |
|:------|:-----------|
| Agent | Claude Code (skill loop) / Claude Desktop (MCP) |
| Backend | Python 3.10+, FastAPI, uvicorn, SQLAlchemy 2.0 async |
| Database | SQLite (default) / PostgreSQL (optional) |
| AI/LLM | DeepSeek (factor generation + cross-review) |
| Browser Automation | Playwright (JoinQuant auto-backtest) |
| Market Data | baostock + akshare (free) → Parquet cache |
| Frontend | React 18 + TypeScript + Tailwind CSS 4 |
| MCP | FastMCP (stdio / SSE / streamable-http) |

---

## License

[MIT](LICENSE)

> **Original Project:** [Miasyster/QuantGPT](https://github.com/Miasyster/QuantGPT) — Agent-Driven LLM Quant Research Engine
>
> This repository is a fork that extends the original project with JoinQuant backtest automation, batch strategy submission, and a validated strategy library.
>
> Copyright (c) 2026 Miasyster. See [NOTICE](NOTICE) for details.

<sub>*Past factor performance does not guarantee future returns. This project does not constitute investment advice.*</sub>
