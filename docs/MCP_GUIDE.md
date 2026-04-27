# QuantGPT MCP 配置指南

QuantGPT 提供标准 MCP (Model Context Protocol) 接口，支持 8 个因子研究工具。可通过 Claude Code、Claude Desktop 等 MCP 客户端直接调用。

## 快速开始（推荐）

### Claude Code

在项目目录下添加 `.mcp.json`：

```json
{
  "mcpServers": {
    "quantgpt": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "quantgpt"],
      "env": {
        "PYTHONPATH": "/path/to/quantgpt",
        "RQDATAC_USERNAME": "your_username",
        "RQDATAC_PASSWORD": "your_password"
      }
    }
  }
}
```

> 注意：`command` 建议使用 Python 绝对路径，如 `/usr/bin/python3`。

验证连接：

```bash
claude mcp list
# quantgpt: connected
```

### Claude Desktop

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`（macOS）：

```json
{
  "mcpServers": {
    "quantgpt": {
      "command": "python3",
      "args": ["-m", "quantgpt"],
      "env": {
        "PYTHONPATH": "/path/to/quantgpt",
        "RQDATAC_USERNAME": "your_username",
        "RQDATAC_PASSWORD": "your_password"
      }
    }
  }
}
```

### 从 GitHub 安装（一键配置）

```bash
# 克隆项目
git clone https://github.com/Miasyster/QuantGPT.git
cd QuantGPT

# 安装依赖
pip install -e .

# 配置数据源（在 .env 中设置米筐账号）
cp .env.example .env
# 编辑 .env，填入 RQDATAC_USERNAME 和 RQDATAC_PASSWORD

# 添加到 Claude Code
claude mcp add quantgpt -s project \
  -e PYTHONPATH=$(pwd) \
  -e RQDATAC_USERNAME=your_username \
  -e RQDATAC_PASSWORD=your_password \
  -- python3 -m quantgpt
```

---

## 工具列表

| 工具 | 说明 |
|------|------|
| `list_operators` | 返回全部因子表达式算子及用法 |
| `list_universes` | 返回可用股票池和基准指数 |
| `validate_expression` | 验证因子表达式语法 |
| `run_backtest` | 执行因子回测，生成 HTML 报告 |
| `score_factor` | 因子综合评分 (0-100, A/B/C/D) |
| `diagnose_factor` | 诊断因子问题，推荐改进策略 |
| `run_anti_overfit` | 反过拟合检测 (4 项测试) |
| `run_rolling_validation` | 滚动验证 (Walk-Forward) |

### 通用参数

以下参数在 `run_backtest`、`score_factor`、`run_anti_overfit`、`run_rolling_validation` 中通用：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `expression` | str | 必填 | 因子表达式 |
| `universe` | str | `hs300` | 股票池：`hs300` / `csi500` / `csi1000` / `csi2000` / `small_scale` |
| `start_date` | str | `2023-01-01` | 回测起始日期 |
| `end_date` | str | `2025-12-31` | 回测结束日期 |
| `n_groups` | int | `5` | 分组数量 |
| `holding_period` | int | `5` | 持仓周期（交易日） |
| `benchmark` | str | `hs300` | 基准指数：`hs300` / `zz500` / `sz50` |
| `neutralize_industry` | bool | `true` | 行业中性化 |
| `neutralize_cap` | bool | `true` | 市值中性化 |

---

## 使用示例

### Agent 工作流

```
1. list_operators         → 了解可用算子
2. 构造因子表达式
3. validate_expression    → 确认语法正确
4. score_factor           → 快速评分
5. run_backtest           → 完整回测 + HTML 报告
6. diagnose_factor        → 诊断改进方向
7. run_anti_overfit       → 检查过拟合风险
8. run_rolling_validation → 样本外验证
```

### 常用因子表达式

```python
# 20日动量
rank(close / ts_mean(close, 20))

# 成交量异动
rank(volume / ts_mean(volume, 10))

# 波动率因子
ts_std(close / ts_shift(close, 1) - 1, 20)

# 反转因子
rank(-1 * ts_delta(close, 5) / ts_shift(close, 5))

# 量价背离
rank(ts_corr(close, volume, 10))

# ROE 动量（基本面）
rank(ts_delta(roe, 60))
```

---

## 股票池

| 名称 | 说明 | 成分股数量 |
|------|------|-----------|
| `small_scale` | 蓝筹测试池 | 5 |
| `hs300` | 沪深300 | ~300 |
| `csi500` | 中证500 | ~500 |
| `csi1000` | 中证1000 | ~1000 |
| `csi2000` | 中证2000 | ~2000 |

---

## 数据源

- **米筐 (rqdatac)**：主数据源，提供行情、因子、股票池数据
- **baostock**：备用数据源
- 首次使用会自动下载并缓存数据到 `data/` 目录，后续直接读取

---

## 远程部署（可选）

QuantGPT 也支持作为远程 HTTP MCP 服务运行：

```bash
# 启动 HTTP 服务（MCP 端点自动挂载到 /mcp）
python -m quantgpt --transport http --port 8002
```

远程 MCP 端点：`http://localhost:8002/mcp`

> 注意：当前 Claude Code 对远程 MCP (type: "http") 的支持尚不稳定，建议优先使用 stdio 模式。
