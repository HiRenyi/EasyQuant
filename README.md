# QuantGPT

用自然语言回测 A 股因子。

输入一句中文描述（如"帮我测试一个20日动量因子"），QuantGPT 通过 LLM 自动生成因子表达式，在 A 股市场执行分组回测，生成 QuantStats HTML 报告，并提供 AI 解读和迭代优化建议。

## 功能特性

- **自然语言驱动** — 中文描述因子逻辑，DeepSeek LLM 自动生成因子表达式；也可直接输入表达式
- **50+ 因子算子** — 支持 rank、zscore、时序函数、条件函数、非线性变换、Alpha101 别名等
- **分组回测引擎** — 按因子值分位数分组，计算多空收益、夏普比率、IC/IR、换手率、单调性等指标
- **反过拟合检测** — IC 稳定性、子样本压力、安慰剂检验、半衰期估计 4 项统计检验
- **因子迭代优化** — 基于诊断的定向突变策略，自动生成并评分候选改进因子
- **AI 因子解读** — 回测完成后自动解读因子经济含义和信号逻辑
- **因子库** — 收藏、管理历史因子，支持模板策略库
- **多因子合成** — 组合多个因子表达式，支持等权/IC 加权/自定义权重
- **因子对比** — 同时回测多个因子，生成相关性矩阵和对比报告
- **滚动验证** — Walk-forward 样本外验证，评估因子稳健性
- **QuantStats 报告** — 自动生成专业级 HTML 回测报告，含基准对比
- **MCP 集成** — 8 个 MCP 工具，接入 Claude Code / Claude Desktop，AI Agent 直接调用
- **Web 前端** — React + Tailwind 界面，SSE 实时推送、会话管理、历史记录
- **Parquet 缓存** — baostock 行情数据本地缓存，避免重复下载

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.10+, FastAPI, uvicorn |
| 数据库 | PostgreSQL（asyncpg + SQLAlchemy 2.0 async + Alembic） |
| 数据源 | baostock（A 股日线行情） |
| 回测 | 自研分组回测 + scipy + QuantStats |
| LLM | DeepSeek（OpenAI 兼容接口） |
| MCP | FastMCP（stdio / SSE / streamable-http） |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS 4 |
| 认证 | JWT（access + refresh token）+ 邮箱验证码 / 密码登录 |

## 项目结构

```
quantgpt/
├── quantgpt/                  # Python 后端包
│   ├── __main__.py            # 入口：MCP / HTTP 服务启动
│   ├── api_server.py          # FastAPI REST API（异步任务 + SSE）
│   ├── mcp_server.py          # FastMCP 服务（8 个 tool）
│   ├── expression_parser.py   # 因子表达式解析器（50+ 算子）
│   ├── backtest.py            # 分组回测引擎（IC/IR/换手率/成本）
│   ├── market_data.py         # baostock 行情获取 + Parquet 缓存
│   ├── report.py              # QuantStats 报告生成
│   ├── iteration.py           # 因子迭代优化（候选生成 + 评分）
│   ├── mutation_engine.py     # 定向突变策略（6 种诊断模式）
│   ├── anti_overfit.py        # 反过拟合检测（4 项统计检验）
│   ├── rolling_validator.py   # Walk-forward 滚动验证
│   ├── composite.py           # 多因子合成引擎
│   ├── attribution.py         # 因子收益归因
│   ├── neutralize.py          # 行业/市值中性化
│   ├── auth.py                # JWT 认证
│   ├── db.py                  # 数据库连接管理
│   ├── models.py              # SQLAlchemy ORM 模型
│   ├── schemas.py             # 共享验证逻辑
│   └── routes/                # 路由模块
│       ├── auth.py            # 登录/注册/Token 刷新
│       ├── sessions.py        # 会话管理
│       ├── factor_library.py  # 因子库（收藏/管理）
│       ├── comparison.py      # 因子对比
│       ├── composite.py       # 多因子合成
│       ├── templates.py       # 策略模板库
│       └── admin.py           # 管理后台
├── frontend/                  # React 前端
│   └── src/
│       ├── App.tsx
│       ├── AppRoutes.tsx
│       ├── api/               # API 客户端（client/auth/factorLibrary/comparison/composite）
│       ├── hooks/             # useBacktest, useTaskHistory, useSession
│       ├── components/        # 表单、进度、结果面板、因子库、对比、合成等
│       ├── pages/             # LoginPage, AdminPage
│       └── types/
├── data/                      # 行情缓存（自动生成）
├── reports/                   # HTML 报告输出（自动生成）
├── deploy/                    # 阿里云 ECS 部署脚本
├── marketing/                 # 知乎推广文章
├── API_DOC.md                 # REST API 文档
├── MCP_GUIDE.md               # MCP 配置指南
├── pyproject.toml
└── restart.sh                 # 一键重启脚本
```

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

### 配置

在项目根目录创建 `.env` 文件：

```env
# LLM
DEEPSEEK_API_KEY=sk-your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# 数据库
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/quantgpt

# 认证
JWT_SECRET_KEY=your-secret-key

# 邮件（验证码登录，可选）
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=noreply@example.com
SMTP_PASSWORD=your-smtp-password
```

### 数据库初始化

```bash
# 使用 Alembic 迁移（推荐）
alembic upgrade head
```

### 数据预热（推荐）

大股票池首次下载耗时较长，建议提前缓存：

```bash
python -m quantgpt --prefetch hs300 csi500
```

### 启动 HTTP 服务（Web 前端 + REST API）

```bash
# 构建前端
cd frontend && npm install && npm run build && cd ..

# 启动服务
python -m quantgpt --transport http --port 8002
```

访问 `http://localhost:8002` 打开前端界面。

或使用一键脚本：

```bash
./restart.sh
```

### 作为 MCP 服务使用（Claude Code）

项目已包含 `.mcp.json` 配置，在项目目录下使用 Claude Code 即可自动连接。

手动添加：

```bash
claude mcp add quantgpt -s project \
  -e PYTHONPATH=/path/to/quantgpt \
  -- python3 -m quantgpt
```

验证连接：

```bash
claude mcp list
# quantgpt: ... - ✓ Connected
```

## 使用方式

### 方式一：Web 前端

打开浏览器访问服务地址，在输入框输入自然语言描述（或直接输入因子表达式），选择股票池和参数，点击提交。页面通过 SSE 实时展示任务进度，完成后显示回测指标、AI 解读和报告链接。支持会话管理、因子库收藏、迭代优化等功能。

### 方式二：REST API

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

### 方式三：MCP（Claude Code / Claude Desktop）

在 Claude 对话中直接使用自然语言，Agent 会自动调用 MCP 工具：

| 工具 | 说明 |
|------|------|
| `list_operators` | 查看可用算子文档 |
| `list_universes` | 查看股票池和基准列表 |
| `validate_expression` | 验证表达式语法 |
| `run_backtest` | 执行回测，生成 HTML 报告 |
| `score_factor` | 快速评分（0-100）和等级（A/B/C/D） |
| `diagnose_factor` | 诊断失败模式，推荐改进策略 |
| `run_anti_overfit` | 4 项反过拟合统计检验 |
| `run_rolling_validation` | Walk-forward 滚动验证 |

详见 [MCP_GUIDE.md](MCP_GUIDE.md)。

## 因子表达式

### 可用算子

| 类别 | 算子 |
|------|------|
| 一元函数 | `rank`, `zscore`, `sign`, `log`, `abs`, `scale`, `tanh`, `sigmoid`, `exp`, `sqrt` |
| 时序函数 | `ts_mean`, `ts_std`, `ts_max`, `ts_min`, `ts_sum`, `ts_shift`, `ts_delta`, `ts_rank`, `ts_argmax`, `ts_argmin`, `decay_linear`, `product` |
| 双列时序 | `ts_corr(col1, col2, N)`, `ts_cov(col1, col2, N)` |
| 非线性 | `power`, `sign_power`, `tanh`, `sigmoid`, `exp`, `sqrt` |
| 条件函数 | `clip(expr, lo, hi)`, `where(cond, t, f)` |
| 算术运算 | `+`, `-`, `*`, `/`, `^` |
| 比较/逻辑 | `>`, `<`, `>=`, `<=`, `==`, `!=`, `and`, `or` |
| 特殊变量 | `vwap`, `returns`, `adv{N}`（如 `adv20`）, `day`, `weekday`, `month` |
| 可用列名 | `open`, `high`, `low`, `close`, `volume`, `amount`, `pct_change` |
| Alpha101 别名 | `delta`, `delay`, `correlation`, `covariance` |

### 示例表达式

```python
# 20日动量
rank(close / ts_mean(close, 20))

# 量价背离
rank(ts_corr(close, volume, 10))

# 非线性动量（复合因子）
sign_power(ts_delta(close, 20) / close, 0.5) * rank(volume / adv20)

# 衰减加权量价相关
decay_linear(rank(ts_corr(vwap, volume, 10)), 5)

# 条件因子
rank(where(ts_rank(volume, 20) > 0.7, ts_delta(close, 10) / close, 0)) * rank(volume / adv20)
```

## 股票池

| 名称 | 说明 | 数据来源 |
|------|------|----------|
| `small_scale` | 5 只蓝筹（茅台、平安、五粮液、美的、招行） | 静态列表 |
| `hs300` | 沪深300成分股 | baostock 动态获取 |
| `csi500` | 中证500成分股 | baostock 动态获取 |

## 回测输出指标

| 指标 | 说明 |
|------|------|
| `total_return` | 总收益 |
| `cagr` | 年化收益率 |
| `sharpe` | 夏普比率 |
| `sortino` | 索提诺比率 |
| `max_drawdown` | 最大回撤 |
| `volatility` | 波动率 |
| `win_rate` | 胜率 |
| `profit_factor` | 盈亏比 |
| `ic_mean` | IC 均值（Pearson） |
| `rank_ic_mean` | Rank IC 均值（Spearman） |
| `ic_ir` | IC 信息比率 |
| `ic_win_rate` | IC 胜率 |
| `long_short_sharpe` | 多空组合夏普 |
| `monotonicity_score` | 分组单调性 (0~1) |
| `spread` | 首尾组收益差 |
| `turnover` | 换手率 |

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DEEPSEEK_API_KEY` | 是（HTTP 模式） | — | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com/v1` | 兼容 OpenAI 接口的 API 地址 |
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

## License

MIT
