# QuantGPT

**用一句中文，回测一个 A 股因子。**

输入"帮我测试一个20日动量因子"，QuantGPT 自动生成因子表达式、执行分组回测、输出 QuantStats 报告，并给出 AI 解读和迭代优化建议。

> 支持 Web 界面 / REST API / MCP（Claude Code & Claude Desktop）三种接入方式。

---

## 它能做什么

```
用户: 帮我测试一个量价背离因子，用沪深300，持仓5天

QuantGPT:
  ✓ 生成表达式  rank(ts_corr(close, volume, 10))
  ✓ 验证语法
  ✓ 拉取行情数据（baostock + Parquet 缓存）
  ✓ 分组回测（5组，IC/IR/换手率/单调性）
  ✓ 反过拟合检测（4项统计检验）
  ✓ 生成 QuantStats HTML 报告
  ✓ AI 解读因子经济含义

  IC均值: 0.032  |  IC_IR: 0.41  |  多空夏普: 1.23  |  单调性: 0.87
```

---

## 核心特性

**自然语言驱动**
中文描述因子逻辑，DeepSeek LLM 自动生成表达式；也可直接输入表达式跳过 LLM。

**50+ 因子算子**
`rank` / `zscore` / `ts_mean` / `ts_corr` / `decay_linear` / `sign_power` / `where` ... 完整支持 Alpha101 别名。

**分组回测引擎**
按因子值分位数分组，自动检测因子方向，计算 IC/IR、多空夏普、换手率、单调性，扣除交易成本（0.3%）。

**反过拟合检测**
IC 稳定性 + 子样本压力 + 安慰剂检验 + 半衰期估计，4 项统计检验一次性跑完。

**因子迭代优化**
诊断失败模式（IC 为零 / IC 为负 / 嵌套过深），生成 6 种定向突变候选，自动评分（0–100，A/B/C/D 等级）。

**Walk-Forward 验证**
滚动训练/验证/测试窗口，评估因子样本外衰减情况。

**多因子合成**
组合多个因子，支持等权 / IC 加权 / 自定义权重。

**MCP 集成**
8 个 MCP 工具，Claude Code / Claude Desktop 直接调用，AI Agent 原生支持。

---

## 快速开始

### 环境要求

- Python >= 3.10
- Node.js >= 18（前端构建）
- PostgreSQL（本地或 Docker）

### 安装

```bash
git clone <repo-url> && cd quantgpt
pip install -e .
```

### 配置 `.env`

```env
# LLM（必填）
DEEPSEEK_API_KEY=sk-your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# 数据库（必填）
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/quantgpt

# 认证（必填）
JWT_SECRET_KEY=your-secret-key

# 邮件验证码登录（可选）
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=noreply@example.com
SMTP_PASSWORD=your-smtp-password
```

### 初始化数据库

```bash
alembic upgrade head
```

### 启动服务

```bash
# 构建前端
cd frontend && npm install && npm run build && cd ..

# 启动
python -m quantgpt --transport http --port 8002
```

访问 `http://localhost:8002`，或直接运行 `./restart.sh`。

### 数据预热（推荐）

首次使用大股票池时，提前缓存行情数据：

```bash
python -m quantgpt --prefetch hs300 csi500
```

---

## 接入方式

### Web 前端

打开浏览器，输入自然语言描述或直接输入因子表达式，选择股票池和参数，提交后通过 SSE 实时查看进度。支持会话管理、因子库收藏、迭代优化、多因子对比等功能。

**主要页面：**
- 单因子回测 — 核心回测流程 + 迭代优化面板
- 策略模板库 — 预置经典因子，一键复用
- 因子榜 — 社区排行榜，一键复刻高分因子
- 多因子组合 — 合成多个因子，支持多种加权方式
- 因子对比 — 相关性矩阵 + 指标横向对比

### REST API

```bash
# 提交回测任务
curl -X POST http://localhost:8002/api/v1/auto_backtest \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "帮我测试一个20日动量因子", "universe": "hs300"}'

# 查询任务状态
curl http://localhost:8002/api/v1/tasks/{task_id} \
  -H "Authorization: Bearer <token>"

# SSE 实时推送
curl "http://localhost:8002/api/v1/tasks/{task_id}/stream?token=<token>"
```

详见 [API_DOC.md](API_DOC.md)。

### MCP（Claude Code / Claude Desktop）

项目根目录已包含 `.mcp.json`，在项目目录下使用 Claude Code 即可自动连接。

手动添加：

```bash
claude mcp add quantgpt -s project \
  -e PYTHONPATH=/path/to/quantgpt \
  -- python3 -m quantgpt
```

**8 个 MCP 工具：**

| 工具 | 说明 |
|------|------|
| `list_operators` | 查看全部算子文档 |
| `list_universes` | 查看股票池和基准列表 |
| `validate_expression` | 验证表达式语法 |
| `run_backtest` | 执行完整回测，生成 HTML 报告 |
| `score_factor` | 快速评分（0–100，A/B/C/D），不生成报告 |
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
| 算术/比较 | `+`, `-`, `*`, `/`, `^`, `>`, `<`, `>=`, `<=`, `==`, `!=`, `and`, `or` |
| 特殊变量 | `vwap`, `returns`, `adv{N}`（如 `adv20`）, `day`, `weekday`, `month` |
| 可用列名 | `open`, `high`, `low`, `close`, `volume`, `amount`, `pct_change` |
| Alpha101 别名 | `delta`, `delay`, `correlation`, `covariance` |

### 示例

```python
# 20日动量
rank(close / ts_mean(close, 20))

# 量价背离
rank(ts_corr(close, volume, 10))

# 非线性动量 × 成交量异常
sign_power(ts_delta(close, 20) / close, 0.5) * rank(volume / adv20)

# 衰减加权量价相关
decay_linear(rank(ts_corr(vwap, volume, 10)), 5)

# 条件因子：高换手时捕捉短期动量
rank(where(ts_rank(volume, 20) > 0.7, ts_delta(close, 10) / close, 0)) * rank(volume / adv20)
```

---

## 股票池

| 名称 | 说明 | 数据来源 |
|------|------|----------|
| `small_scale` | 5 只蓝筹（快速测试用） | 静态列表 |
| `hs300` | 沪深300成分股 | baostock 动态获取 |
| `csi500` | 中证500成分股 | baostock 动态获取 |
| `csi1000` | 中证1000成分股 | baostock 动态获取 |
| `csi2000` | 中证2000成分股 | baostock 动态获取 |

基准指数：`hs300` / `zz500` / `sz50`

---

## 回测输出指标

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
├── quantgpt/                  # Python 后端
│   ├── api_server.py          # FastAPI REST API（异步任务 + SSE）
│   ├── mcp_server.py          # FastMCP 服务（8 个工具）
│   ├── backtest.py            # 分组回测引擎
│   ├── expression_parser.py   # 因子表达式解析器（50+ 算子）
│   ├── market_data.py         # baostock 行情 + Parquet 缓存
│   ├── report.py              # QuantStats 报告生成
│   ├── iteration.py           # 因子迭代优化
│   ├── mutation_engine.py     # 定向突变策略（6 种模式）
│   ├── anti_overfit.py        # 反过拟合检测（4 项检验）
│   ├── rolling_validator.py   # Walk-forward 滚动验证
│   ├── composite.py           # 多因子合成
│   ├── neutralize.py          # 行业/市值中性化
│   └── routes/                # auth / sessions / factor_library /
│                              # comparison / composite / templates / admin
├── frontend/src/              # React 18 + TypeScript + Vite + Tailwind CSS 4
│   ├── components/            # 20+ 组件
│   ├── hooks/                 # useBacktest / useTaskHistory / useSession
│   └── api/                   # API 客户端层
├── deploy/                    # 阿里云 ECS 部署脚本
├── data/                      # 行情缓存（自动生成）
├── reports/                   # HTML 报告输出（自动生成）
├── API_DOC.md                 # REST API 文档
├── MCP_GUIDE.md               # MCP 配置指南
└── restart.sh                 # 一键重启
```

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.10+, FastAPI, uvicorn |
| 数据库 | PostgreSQL（asyncpg + SQLAlchemy 2.0 async + Alembic） |
| 数据源 | baostock（A 股日线行情） |
| 回测 | 自研分组回测 + scipy + QuantStats |
| LLM | DeepSeek（OpenAI 兼容接口，可替换） |
| MCP | FastMCP（stdio / SSE / streamable-http） |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS 4 |
| 认证 | JWT（access + refresh token）+ 邮箱验证码 |

---

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DEEPSEEK_API_KEY` | 是 | — | LLM API Key |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com/v1` | 兼容 OpenAI 接口地址 |
| `DEEPSEEK_MODEL` | 否 | `deepseek-chat` | 模型名称 |
| `DATABASE_URL` | 是 | — | PostgreSQL 连接串（asyncpg 格式） |
| `JWT_SECRET_KEY` | 是 | — | JWT 签名密钥 |
| `JWT_ACCESS_TOKEN_EXPIRE_HOURS` | 否 | `24` | Access Token 有效期（小时） |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | 否 | `7` | Refresh Token 有效期（天） |
| `SMTP_HOST` | 否 | — | 邮件服务器（验证码登录） |
| `SMTP_PORT` | 否 | `465` | 邮件服务器端口 |
| `SMTP_USER` | 否 | — | 发件人邮箱 |
| `SMTP_PASSWORD` | 否 | — | 邮件密码 |
| `QUANTGPT_MAX_ACTIVE_TASKS` | 否 | `5` | 最大并发任务数 |
| `QUANTGPT_RATE_LIMIT` | 否 | `10` | 每 IP 每分钟请求上限 |
| `QUANTGPT_CORS_ORIGINS` | 否 | `*` | CORS 允许的域名 |
| `QUANTGPT_FEEDBACK_WEBHOOK` | 否 | — | 飞书 Webhook URL（用户反馈通知） |

---

## License

MIT
