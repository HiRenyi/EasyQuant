# QuantGPT

用自然语言回测 A 股因子。

输入一句话描述（如"帮我测试一个20日动量因子"），QuantGPT 通过 LLM 自动生成因子表达式，在 A 股市场执行分组回测，生成 QuantStats HTML 报告。

## 功能特性

- **自然语言驱动** — 用户用中文描述因子逻辑，DeepSeek LLM 自动生成因子表达式
- **50+ 因子算子** — 支持 rank、zscore、时序函数、条件函数、Alpha101 别名等
- **分组回测引擎** — 按因子值分位数分组，计算多空收益、夏普比率、单调性等指标
- **QuantStats 报告** — 自动生成专业级 HTML 回测报告
- **MCP 集成** — 作为 MCP 服务接入 Claude Code / Claude Desktop，AI Agent 直接调用
- **Web 前端** — React + Tailwind 界面，提交任务、SSE 实时推送、查看报告
- **Parquet 缓存** — baostock 行情数据本地缓存，避免重复下载

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.10+, FastAPI, uvicorn |
| 数据源 | baostock（A 股日线行情） |
| 回测 | 自研分组回测 + scipy + QuantStats |
| LLM | DeepSeek（OpenAI 兼容接口） |
| MCP | FastMCP（stdio / SSE / streamable-http） |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS 4 |

## 项目结构

```
quantgpt/
├── quantgpt/                  # Python 后端包
│   ├── __main__.py            # 入口：MCP / HTTP 服务启动
│   ├── api_server.py          # FastAPI REST API（异步任务 + SSE）
│   ├── mcp_server.py          # FastMCP 服务（4 个 tool）
│   ├── expression_parser.py   # 因子表达式解析器
│   ├── backtest.py            # 分组回测引擎
│   ├── market_data.py         # baostock 行情获取 + Parquet 缓存
│   └── report.py              # QuantStats 报告生成
├── frontend/                  # React 前端
│   └── src/
│       ├── App.tsx
│       ├── api/client.ts      # API 客户端
│       ├── hooks/             # useBacktest, useTaskHistory
│       ├── components/        # 表单、进度、结果面板、历史记录
│       └── types/
├── data/                      # 行情缓存（自动生成）
├── reports/                   # HTML 报告输出（自动生成）
├── API_DOC.md                 # REST API 文档
├── MCP_GUIDE.md               # MCP 配置指南
├── pyproject.toml
└── restart.sh                 # 一键重启脚本
```

## 快速开始

### 环境要求

- Python >= 3.10
- Node.js >= 18（前端构建）

### 安装

```bash
git clone <repo-url> && cd quantgpt
pip install -e .
```

### 配置

在项目根目录创建 `.env` 文件：

```env
DEEPSEEK_API_KEY=sk-your-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
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

打开浏览器访问服务地址，在输入框输入自然语言描述，选择股票池和参数，点击提交。页面通过 SSE 实时展示任务进度，完成后显示回测指标和报告链接。

### 方式二：REST API

```bash
# 提交回测任务
curl -X POST http://localhost:8002/api/v1/auto_backtest \
  -H "Content-Type: application/json" \
  -d '{"prompt": "帮我测试一个20日动量因子", "universe": "small_scale"}'

# 查询任务状态
curl http://localhost:8002/api/v1/tasks/{task_id}

# SSE 实时推送
curl http://localhost:8002/api/v1/tasks/{task_id}/stream
```

详见 [API_DOC.md](API_DOC.md)。

### 方式三：MCP（Claude Code / Claude Desktop）

在 Claude 对话中直接使用自然语言，Agent 会自动调用 MCP 工具：

```
1. list_operators    → 查看可用算子
2. validate_expression → 验证表达式语法
3. run_backtest      → 执行回测，获取报告
```

详见 [MCP_GUIDE.md](MCP_GUIDE.md)。

## 因子表达式

### 可用算子

| 类别 | 算子 |
|------|------|
| 一元函数 | `rank`, `zscore`, `sign`, `log`, `abs`, `scale`, `tanh`, `sigmoid`, `exp`, `sqrt` |
| 时序函数 | `ts_mean`, `ts_std`, `ts_max`, `ts_min`, `ts_sum`, `ts_shift`, `ts_delta`, `ts_rank`, `ts_argmax`, `ts_argmin`, `decay_linear`, `product` |
| 双列时序 | `ts_corr(col1, col2, N)`, `ts_cov(col1, col2, N)` |
| 二元函数 | `power`, `sign_power`, `max`, `min` |
| 条件函数 | `clip(expr, lo, hi)`, `where(cond, t, f)` |
| 算术运算 | `+`, `-`, `*`, `/`, `^` |
| 比较运算 | `>`, `<`, `>=`, `<=`, `==`, `!=` |
| 特殊变量 | `vwap`, `returns`, `adv{N}`（如 `adv20`） |
| 可用列名 | `open`, `high`, `low`, `close`, `volume`, `amount`, `pct_change` |

### 示例表达式

```python
# 20日动量
rank(close/ts_mean(close, 20))

# 成交量异动
rank(volume/ts_mean(volume, 10))

# 波动率因子
ts_std(close/ts_shift(close, 1) - 1, 20)

# 反转因子
rank(-1 * ts_delta(close, 5) / ts_shift(close, 5))

# 量价背离
rank(ts_corr(close, volume, 10))
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
| `long_short_sharpe` | 多空组合夏普 |
| `monotonicity_score` | 分组单调性 (0~1) |
| `spread` | 首尾组收益差 |

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DEEPSEEK_API_KEY` | 是（HTTP 模式） | — | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com/v1` | 兼容 OpenAI 接口的 API 地址 |
| `DEEPSEEK_MODEL` | 否 | `deepseek-chat` | 模型名称 |
| `QUANTGPT_MAX_ACTIVE_TASKS` | 否 | `5` | 最大并发任务数 |
| `QUANTGPT_RATE_LIMIT` | 否 | `10` | 每 IP 每分钟请求上限 |
| `QUANTGPT_CORS_ORIGINS` | 否 | `*` | CORS 允许的域名 |

## License

MIT
