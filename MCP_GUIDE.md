# QuantGPT MCP 配置与使用说明

QuantGPT — 用自然语言回测 A 股因子。支持本地 stdio 和远程 HTTP 两种传输模式。

## 目录

- [安装](#安装)
- [传输模式](#传输模式)
- [场景一：本地 Claude Code (stdio)](#场景一本地-claude-code-stdio)
- [场景二：远程 HTTP 服务 (OpenClaw / 其他 MCP 客户端)](#场景二远程-http-服务-openclaw--其他-mcp-客户端)
- [工具列表](#工具列表)
- [使用示例](#使用示例)
- [数据与报告路径](#数据与报告路径)

---

## 安装

```bash
cd /Users/macbook/Projects/my_python_project/simple-backtest
pip install -e .
```

## 传输模式

| 模式 | 命令 | 适用场景 |
|------|------|----------|
| `stdio` | `python -m quantgpt` | 本地 Claude Code / Claude Desktop |
| `streamable-http` | `python -m quantgpt --transport streamable-http --port 8000` | OpenClaw / 远程客户端 |
| `sse` | `python -m quantgpt --transport sse --port 8000` | 旧版 MCP 客户端 |

<!-- PLACEHOLDER_SECTION_1 -->

---

## 场景一：本地 Claude Code (stdio)

项目根目录 `.mcp.json` 已包含配置：

```json
{
  "mcpServers": {
    "quantgpt": {
      "type": "stdio",
      "command": "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
      "args": ["-m", "quantgpt"],
      "env": {
        "PYTHONPATH": "/Users/macbook/Projects/my_python_project/simple-backtest"
      }
    }
  }
}
```

> `command` 必须使用 Python 绝对路径，`python` 是 zsh alias，MCP 子进程无法识别。

验证：

```bash
claude mcp list
# quantgpt: ... - ✓ Connected
```

CLI 管理：

```bash
# 添加
claude mcp add quantgpt -s project \
  -e PYTHONPATH=/Users/macbook/Projects/my_python_project/simple-backtest \
  -- /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m quantgpt

# 移除
claude mcp remove quantgpt -s project
```

---

<!-- PLACEHOLDER_SECTION_2 -->

## 场景二：远程 HTTP 服务 (OpenClaw / 其他 MCP 客户端)

将 QuantGPT 作为远程 HTTP MCP 服务运行，供 OpenClaw Gateway 或任何支持 Streamable HTTP 的 MCP 客户端调用。

### 架构

```
┌──────────────────────┐       HTTPS        ┌──────────────────────────┐
│  OpenClaw Gateway    │ ◄────────────────► │  QuantGPT                │
│  (MCP Client)        │   Streamable HTTP  │  MCP Server :8000        │
│                      │   POST /mcp        │                          │
│  或其他 MCP 客户端    │                    │  4 tools:                │
│  (Claude.ai 等)      │                    │  - list_operators        │
└──────────────────────┘                    │  - list_universes        │
                                            │  - validate_expression   │
                                            │  - run_backtest          │
                                            └──────────────────────────┘
```

### 步骤 1：启动 HTTP MCP Server

```bash
cd /Users/macbook/Projects/my_python_project/simple-backtest

# Streamable HTTP（推荐，MCP 2025-03-26 规范）
python -m quantgpt --transport streamable-http --host 0.0.0.0 --port 8000

# 或 SSE（兼容旧版客户端）
python -m quantgpt --transport sse --host 0.0.0.0 --port 8000
```

服务启动后，MCP 端点地址为：

| 传输模式 | 端点 URL |
|----------|----------|
| streamable-http | `http://<服务器IP>:8000/mcp` |
| sse | `http://<服务器IP>:8000/sse` |

### 步骤 2：验证服务可用

```bash
# 发送 MCP initialize 请求测试
curl -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0"}
    }
  }'
```

预期返回包含 `serverInfo.name: "quantgpt"` 和 4 个 tools。

### 步骤 3：在 OpenClaw 中配置

OpenClaw 通过 `mcporter` 管理远程 MCP 连接。在 OpenClaw 配置中添加：

```json
{
  "mcpServers": {
    "quantgpt": {
      "url": "http://<服务器IP>:8000/mcp",
      "transport": "streamable-http"
    }
  }
}
```

如果使用 SSE 传输：

```json
{
  "mcpServers": {
    "quantgpt": {
      "url": "http://<服务器IP>:8000/sse",
      "transport": "sse"
    }
  }
}
```

### 步骤 4（可选）：生产部署

#### 使用 systemd 守护进程

```ini
# /etc/systemd/system/quantgpt.service
[Unit]
Description=QuantGPT MCP Server
After=network.target

[Service]
Type=simple
User=macbook
WorkingDirectory=/Users/macbook/Projects/my_python_project/simple-backtest
Environment=PYTHONPATH=/Users/macbook/Projects/my_python_project/simple-backtest
ExecStart=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m quantgpt --transport streamable-http --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now quantgpt
```

#### 使用 Nginx 反向代理 + HTTPS

```nginx
server {
    listen 443 ssl;
    server_name backtest.your-domain.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /mcp {
        proxy_pass http://127.0.0.1:8000/mcp;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_buffering off;           # SSE/streaming 必须关闭缓冲
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

配置 HTTPS 后，OpenClaw 端改为：

```json
{
  "mcpServers": {
    "quantgpt": {
      "url": "https://backtest.your-domain.com/mcp",
      "transport": "streamable-http"
    }
  }
}
```

<!-- PLACEHOLDER_SECTION_3 -->

---

## 工具列表

| 工具 | 说明 | 参数 |
|------|------|------|
| `list_operators` | 返回全部因子表达式算子及用法 | 无 |
| `list_universes` | 返回可用股票池和基准指数 | 无 |
| `validate_expression` | 验证因子表达式语法 | `expression: str` |
| `run_backtest` | 执行因子回测，生成 HTML 报告 | 见下方 |

### run_backtest 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `expression` | str | 必填 | 因子表达式，如 `rank(close/ts_mean(close, 20))` |
| `universe` | str | `hs300` | 股票池：`small_scale` / `hs300` / `csi500` |
| `start_date` | str | `2022-01-01` | 回测起始日期 |
| `end_date` | str | `2024-12-31` | 回测结束日期 |
| `n_groups` | int | `5` | 分位数分组数量 |
| `holding_period` | int | `5` | 持仓周期（交易日） |
| `benchmark` | str | `hs300` | 基准指数：`hs300` / `zz500` / `sz50` |

### run_backtest 返回值

```json
{
  "report_path": "HTML 报告绝对路径",
  "metrics": {
    "total_return": "总收益",
    "cagr": "年化收益率",
    "sharpe": "夏普比率",
    "sortino": "索提诺比率",
    "max_drawdown": "最大回撤",
    "volatility": "波动率",
    "win_rate": "胜率",
    "profit_factor": "盈亏比"
  },
  "backtest_summary": {
    "long_short_sharpe": "多空组合夏普",
    "monotonicity_score": "分组单调性 (0~1)",
    "spread": "首尾组收益差",
    "group_returns": { "0": {"mean_return": 0.001, "sharpe": 0.2}, "...": "..." }
  }
}
```

---

## 使用示例

### Agent 工作流

```
1. list_operators    → 了解可用算子
2. 构造因子表达式
3. validate_expression → 确认语法正确
4. run_backtest      → 获取回测结果和报告路径
```

### 常用因子表达式

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

### 股票池

| 名称 | 说明 | 数据来源 |
|------|------|----------|
| `small_scale` | 5 只蓝筹（茅台、平安、五粮液、美的、招行） | 静态列表 |
| `hs300` | 沪深300成分股 | baostock 动态获取 |
| `csi500` | 中证500成分股 | baostock 动态获取 |

首次使用 `hs300` / `csi500` 会从 baostock 下载行情数据，耗时较长。数据缓存在 `data/` 目录，后续直接读取。

---

## 数据与报告路径

```
simple-backtest/
├── data/
│   ├── stocks/          # 个股行情 Parquet 缓存
│   └── benchmark/       # 基准指数缓存
└── reports/             # QuantStats HTML 报告输出
```

远程部署时，HTML 报告生成在服务器本地 `reports/` 目录。如需客户端访问报告文件，可额外配置 Nginx 静态文件服务：

```nginx
location /reports/ {
    alias /Users/macbook/Projects/my_python_project/simple-backtest/reports/;
    autoindex on;
}
```
