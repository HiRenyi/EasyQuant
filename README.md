# QuantGPT

**用一句中文，挖掘可直接提交 WorldQuant BRAIN 的 alpha 因子。**

输入"找一个基于价量背离的短期反转因子"，QuantGPT 自动生成因子表达式、执行 A 股分组回测、输出完整报告——产出的因子直接复制到 BRAIN 验证，Sharpe 1.73，通过 6/7 项 IS Testing。

> Web 界面 / REST API / MCP（Claude Code & Claude Desktop）三种接入方式。

---

## 先看结果

3 轮迭代、24 个候选表达式，产出以下因子并在 WorldQuant BRAIN 上完成独立验证：

| 因子 | 表达式 | A股 Sharpe | 美股 Sharpe | BRAIN IS | 核心优势 |
|------|--------|-----------|-----------|----------|---------|
| 短窗口价量背离 | `-1 * rank(ts_corr(close, volume, 5))` | 1.42 | **1.73** | 6/7 PASS | 收益最强 |
| 中窗口价量背离 | `-1 * rank(ts_corr(close, volume, 10))` | 0.66 | 0.91 | 4/7 PASS | 低换手 |
| 双价量背离 | `rank(-1*ts_corr(close,volume,5))*rank(-1*ts_corr(high,volume,10))` | 0.87 | 1.20 | 6/7 PASS | 最稳定 |

三个因子在 A 股和美股两个完全独立的市场上均表现有效——**价量背离是跨市场的稳健 alpha 来源**。

系统已累计执行超过 **370 次**回测任务，单轮迭代 8 个候选因子约 15 分钟。

<p align="center">
  <img src="example_factor/2-1.png" width="48%" alt="BRAIN PnL 曲线" />
  <img src="example_factor/2-2.png" width="48%" alt="BRAIN IS Testing" />
</p>
<p align="center"><em>WorldQuant BRAIN 验证：Factor 1 PnL 曲线 + IS Testing Summary</em></p>

更多因子详情和 BRAIN 验证截图见 [`example_factor/`](example_factor/)。

---

## 与 WorldQuant BRAIN 的关系

所有因子表达式采用 **WorldQuant BRAIN 算子标准**（`rank`、`ts_corr`、`ts_rank`、`decay_linear` 等），这意味着：

1. QuantGPT 挖掘出的因子，**可以直接复制到 BRAIN 平台验证**，无需任何格式转换
2. BRAIN 用完全独立的数据源（美股 TOP3000）和回测引擎做验证，结果具备第三方公信力
3. QuantGPT 的评级体系与 BRAIN 的质量标准高度一致：

| QuantGPT 评级 | 对应 BRAIN 表现 | 示例 |
|--------------|----------------|------|
| **A 级** | Sharpe 1.5+，6/7 PASS，接近可提交 | Factor 1 (Sharpe 1.73) |
| **B 级** | Sharpe 0.9–1.2，4–6/7 PASS | Factor 2、Factor 3 |

---

## 核心特性

**自然语言驱动**
中文描述因子逻辑，LLM 自动生成表达式；也可直接输入表达式跳过 LLM。

**50+ 因子算子**
`rank` / `zscore` / `ts_mean` / `ts_corr` / `decay_linear` / `sign_power` / `where` ... 完整支持 WorldQuant BRAIN 算子标准和 Alpha101 别名。

**分组回测引擎**
按因子值分位数分组，自动检测因子方向，计算 IC/IR、多空夏普、换手率、单调性，扣除交易成本。

**反过拟合检测**
IC 稳定性 + 子样本压力（牛/熊/震荡）+ 安慰剂检验 + 半衰期估计，4 项统计检验。

**因子迭代引擎**
三阶段演化：轨迹分析 → 元演化策略选择（8 种变异方向）→ LLM 候选生成。5 维评分：IC 均值 + IC_IR + 稳定性 + 抗过拟合 + 分组回测。

**Walk-Forward 验证**
滚动训练/验证/测试窗口，评估因子样本外衰减。

**多因子合成**
组合多个因子，支持等权 / IC 加权 / 自定义权重。

**策略回测**
自然语言生成完整交易策略代码，对接聚宽平台执行回测。

**每日量化日报**
自动生成 A 股市场日报，包含行业轮动分析和因子信号。

**模拟盘**
基于因子信号的模拟组合，每日自动结算并跟踪收益。

**MCP 集成**
8 个 MCP 工具，Claude Code / Claude Desktop 直接调用回测引擎，让 AI Agent 原生具备因子研究能力。

---

## 快速开始

### 环境要求

- Python >= 3.10
- Node.js >= 18（前端构建）
- PostgreSQL（本地或 Docker）
- DeepSeek API Key（[注册送免费额度](https://platform.deepseek.com)）

### 安装

```bash
git clone https://github.com/Miasyster/QuantGPT.git && cd QuantGPT
pip install -e .
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key 和 PostgreSQL 连接信息
```

最低配置只需填 3 项：

```env
DEEPSEEK_API_KEY=sk-your-api-key
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/quantgpt
JWT_SECRET_KEY=your-secret-key
```

### 初始化数据库

```bash
# Docker 快速创建 PostgreSQL（可选）
docker run -d --name quantgpt-pg \
  -e POSTGRES_USER=quantgpt -e POSTGRES_PASSWORD=password -e POSTGRES_DB=quantgpt \
  -p 5432:5432 postgres:16-alpine

# 执行迁移
alembic upgrade head
```

### 启动

```bash
cd frontend && npm install && npm run build && cd ..
python -m quantgpt --transport http --port 8002
```

打开 `http://localhost:8002` 即可使用。也可直接运行 `./restart.sh` 一键构建并启动。

---

## 接入方式

### Web 前端

React 18 + TypeScript + Tailwind CSS 4 全功能 SPA，支持深色模式。

**主要功能：**
- 因子回测 — 自然语言输入 + SSE 实时进度 + 完整报告
- 因子迭代 — 诊断失败模式，自动生成变异候选
- 策略回测 — 自然语言生成交易策略并执行回测
- 因子库 — 收藏因子，一键复用
- 多因子合成 — 组合多个因子，支持多种加权方式
- 因子对比 — 相关性矩阵 + 指标横向对比
- 模拟盘 — 基于因子信号的模拟组合跟踪
- 每日日报 — A 股市场概况 + 行业轮动 + 因子信号

### REST API

```bash
# 提交回测任务
curl -X POST http://localhost:8002/api/v1/auto_backtest \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "帮我测试一个20日动量因子", "universe": "hs300"}'

# SSE 实时推送
curl "http://localhost:8002/api/v1/tasks/{task_id}/stream?token=<token>"
```

详见 [API_DOC.md](API_DOC.md)。

### MCP（Claude Code / Claude Desktop）

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

在 Claude 里说"帮我在中证500上测试一个低波动率因子"，它直接调用 `run_backtest` 返回结果。

**8 个 MCP 工具：**

| 工具 | 说明 |
|------|------|
| `list_operators` | 查看全部算子文档 |
| `list_universes` | 查看股票池和基准列表 |
| `validate_expression` | 验证表达式语法 |
| `run_backtest` | 执行完整回测 |
| `score_factor` | 快速评分（0–100，A/B/C/D） |
| `diagnose_factor` | 诊断失败模式，推荐改进策略 |
| `run_anti_overfit` | 4 项反过拟合统计检验 |
| `run_rolling_validation` | Walk-forward 滚动验证 |

详见 [MCP_GUIDE.md](MCP_GUIDE.md)。

---

## 因子表达式

### 算子速查

| 类别 | 算子 |
|------|------|
| 截面变换 | `rank`, `zscore`, `sign`, `log`, `abs`, `scale`, `tanh`, `sigmoid`, `exp`, `sqrt` |
| 时序函数 | `ts_mean`, `ts_std`, `ts_max`, `ts_min`, `ts_sum`, `ts_shift`, `ts_delta`, `ts_rank`, `ts_argmax`, `ts_argmin`, `decay_linear`, `product` |
| 双列时序 | `ts_corr(col1, col2, N)`, `ts_cov(col1, col2, N)` |
| 非线性 | `power`, `sign_power` |
| 条件函数 | `clip(expr, lo, hi)`, `where(cond, t, f)` |
| 技术指标 | `rsi`, `ema`, `macd`, `boll_upper`, `boll_lower`, `atr` |
| 算术/比较 | `+`, `-`, `*`, `/`, `^`, `>`, `<`, `>=`, `<=`, `==`, `!=`, `and`, `or` |
| 特殊变量 | `vwap`, `returns`, `adv{N}`, `day`, `weekday`, `month` |
| 可用列名 | `open`, `high`, `low`, `close`, `volume`, `amount`, `pct_change` |
| 基本面 | `roe`, `pe`, `pb` 等 23 个财务变量（需 rqdatac 数据源） |
| Alpha101 别名 | `delta`, `delay`, `correlation`, `covariance` |

### 示例

```
# 20日动量
rank(close / ts_mean(close, 20))

# 量价背离（BRAIN 验证 Sharpe 1.73）
-1 * rank(ts_corr(close, volume, 5))

# 低波动率
rank(-1 * ts_std(close/ts_shift(close,1)-1, 20))

# RSI 超卖
where(rsi(close, 14) < 30, 1, 0)

# 衰减加权量价相关
decay_linear(rank(ts_corr(vwap, volume, 10)), 5)
```

---

## 股票池

| 名称 | 说明 |
|------|------|
| `small_scale` | 5 只蓝筹（快速测试） |
| `hs300` | 沪深300成分股 |
| `csi500` | 中证500成分股 |
| `csi1000` | 中证1000成分股 |
| `csi2000` | 中证2000成分股 |

基准指数：`hs300` / `zz500` / `sz50`

数据源：baostock（免费，无需注册）为默认数据源，rqdatac（米筐）为可选高级数据源。行情数据以 Parquet 格式本地缓存，避免重复拉取。

---

## 回测指标

| 指标 | 说明 |
|------|------|
| `ic_mean` / `rank_ic_mean` | IC 均值（Pearson / Spearman） |
| `ic_ir` | IC 信息比率 |
| `ic_win_rate` | IC 胜率 |
| `long_short_sharpe` | 多空组合夏普 |
| `monotonicity_score` | 分组单调性（0~1） |
| `spread` | 首尾组收益差 |
| `turnover` | 换手率 |
| `sharpe` / `sortino` | 夏普 / 索提诺比率 |
| `max_drawdown` | 最大回撤 |
| `cagr` | 年化收益率 |

---

## 项目结构

```
quantgpt/
├── quantgpt/                    # Python 后端
│   ├── api_server.py            # FastAPI REST API + SSE
│   ├── mcp_server.py            # FastMCP 服务（8 个工具）
│   ├── expression_parser.py     # 因子表达式解析器（50+ 算子，WQ BRAIN 兼容）
│   ├── backtest.py              # 分组回测引擎
│   ├── market_data.py           # 行情数据（baostock + rqdatac + Parquet 缓存）
│   ├── report.py                # QuantStats HTML 报告
│   ├── iteration.py             # 因子迭代优化（三阶段演化）
│   ├── mutation_engine.py       # 定向突变策略（8 种模式）
│   ├── trajectory_analyzer.py   # 迭代轨迹分析
│   ├── meta_evolution.py        # 元演化策略选择
│   ├── crossover_engine.py      # 因子交叉引擎
│   ├── anti_overfit.py          # 反过拟合检测（4 项检验）
│   ├── rolling_validator.py     # Walk-forward 滚动验证
│   ├── composite.py             # 多因子合成
│   ├── neutralize.py            # 行业/市值中性化
│   ├── daily_summary.py         # 每日量化日报
│   ├── paper_engine.py          # 模拟盘引擎
│   ├── jq_automation.py         # 聚宽策略回测自动化（Playwright）
│   ├── strategy_prompt.py       # 策略代码生成提示词
│   └── routes/                  # API 路由模块
├── frontend/                    # React 18 + TypeScript + Vite + Tailwind CSS 4
├── tests/                       # 单元测试（表达式解析器 + 回测引擎）
├── example_factor/              # 因子展示（含 WorldQuant BRAIN 验证截图）
├── deploy/                      # 部署脚本
├── .env.example                 # 环境变量模板
├── API_DOC.md                   # REST API 文档
├── MCP_GUIDE.md                 # MCP 配置指南
└── restart.sh                   # 一键重启
```

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.10+, FastAPI, uvicorn |
| 数据库 | PostgreSQL (asyncpg + SQLAlchemy 2.0 async + Alembic) |
| LLM | DeepSeek（OpenAI 兼容接口，可替换任意兼容模型） |
| 行情数据 | baostock（免费 A 股日线）+ rqdatac（可选）+ Parquet 缓存 |
| 报告 | QuantStats HTML |
| MCP | FastMCP（stdio / SSE / streamable-http） |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS 4 |
| 认证 | JWT（access + refresh token）+ 邮箱验证码 |
| 策略回测 | Playwright + 聚宽平台自动化（可选） |

---

## 和其他工具的对比

| | 聚宽/掘金 | Backtrader | vnpy | QuantGPT |
|---|---|---|---|---|
| 上手方式 | 写 Python | 写 Python | 写 Python | 说一句中文 |
| 因子回测 | 需自己写 | 需自己写 | 不支持 | 自然语言一键 |
| AI 生成因子 | 无 | 无 | 无 | ✅ LLM 驱动 |
| 因子评分 | 无 | 无 | 无 | ✅ 5 维自动评分 |
| 抗过拟合检测 | 无 | 无 | 无 | ✅ 4 项统计检验 |
| WQ BRAIN 兼容 | 无 | 无 | 无 | ✅ 算子标准对齐 |
| MCP / AI Agent | 无 | 无 | 无 | ✅ 8 个工具 |
| 开源 | 部分 | ✅ | ✅ | ✅ MIT |
| 实盘对接 | ✅ | 有限 | ✅ | 无 |
| 分钟级数据 | ✅ | ✅ | ✅ | 仅日频 |

---

## 已知限制

1. **仅日频数据** — 不支持分钟级回测，不适合日内策略
2. **单体架构** — 内存任务队列，不支持水平扩展
3. **策略回测依赖聚宽** — 需要聚宽账号 + Playwright 自动化（可选功能）

---

## 环境变量

完整列表见 [`.env.example`](.env.example)。

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | 是 | LLM API Key |
| `DATABASE_URL` | 是 | PostgreSQL 连接串（asyncpg 格式） |
| `JWT_SECRET_KEY` | 是 | JWT 签名密钥 |
| `DEEPSEEK_BASE_URL` | 否 | LLM API 地址（默认 DeepSeek） |
| `DEEPSEEK_MODEL` | 否 | 模型名称（默认 deepseek-chat） |
| `RQDATAC_USERNAME` | 否 | 米筐数据源账号（高级数据） |
| `JQ_USERNAME` | 否 | 聚宽账号（策略回测功能） |
| `SMTP_HOST` | 否 | 邮件服务器（验证码登录） |

---

## Contributing

欢迎提 Issue 和 PR：

- 🐛 Bug 反馈 / 功能建议
- 🔀 改进引擎、补测试、加算子
- 📖 完善文档

---

## License

[MIT](LICENSE)

---

*因子回测的历史表现不代表未来收益。本项目不构成投资建议。*
