# 用 Claude + MCP 三分钟搭建 A 股因子回测工具

> 本文介绍如何使用 QuantGPT 的 MCP (Model Context Protocol) 服务，让 Claude 成为你的量化研究助手。

## 什么是 MCP？

MCP（Model Context Protocol）是 Anthropic 推出的开放协议，让 AI 模型能直接调用外部工具。通过 MCP，Claude 不再只是一个聊天机器人——它可以查询数据、执行计算、生成报告。

QuantGPT 提供了 4 个 MCP 工具，让 Claude 具备完整的 A 股因子回测能力。

## 快速开始

### 1. 安装 QuantGPT

```bash
git clone https://github.com/your-repo/quantgpt.git
cd quantgpt
pip install -e .
```

### 2. 配置 Claude Code

在项目根目录创建 `.mcp.json`：

```json
{
  "mcpServers": {
    "quantgpt": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "quantgpt"],
      "env": {
        "PYTHONPATH": "/path/to/quantgpt"
      }
    }
  }
}
```

验证连接：

```bash
claude mcp list
# quantgpt: ... - ✓ Connected
```

### 3. 开始对话

直接用自然语言告诉 Claude 你想测试什么因子：

```
我想测试一个 20 日动量因子，在沪深 300 上回测 2023-2025 年的表现
```

Claude 会自动：
1. 调用 `list_operators` 了解可用算子
2. 生成因子表达式 `rank(close / ts_mean(close, 20))`
3. 调用 `validate_expression` 验证语法
4. 调用 `run_backtest` 执行回测
5. 分析结果并给出改进建议

## 四个核心工具

| 工具 | 功能 | 典型用法 |
|------|------|----------|
| `list_operators` | 查看 30+ 算子列表 | "有哪些可用的时序算子？" |
| `list_universes` | 查看股票池和基准 | "支持哪些股票池？" |
| `validate_expression` | 验证表达式语法 | 自动调用，确保表达式正确 |
| `run_backtest` | 执行分组回测 | "回测这个因子在中证 500 上的表现" |

## 实战：让 Claude 帮你做因子研究

### 场景 1：探索性研究

```
帮我测试几个经典因子：
1. 20日动量
2. 成交量异动
3. 波动率因子
4. 量价背离

在沪深300上回测2023-2025年，5日持仓，帮我比较哪个表现最好。
```

Claude 会依次回测每个因子，对比 Sharpe、IC、单调性等指标，给出分析。

### 场景 2：因子改进

```
这个动量因子 Sharpe 只有 0.3，有什么改进思路？帮我试试加入成交量加权。
```

Claude 会基于诊断结果，生成改进版表达式并回测验证。

### 场景 3：组合构建

```
帮我用动量因子和反转因子做一个等权组合，看看组合后的表现。
```

## 远程部署：团队共享

QuantGPT 支持 HTTP 模式，可以部署到服务器让团队共用：

```bash
# 在服务器上启动
python -m quantgpt --transport streamable-http --host 0.0.0.0 --port 8000
```

其他人在 Claude Code 中配置远程连接即可使用：

```json
{
  "mcpServers": {
    "quantgpt": {
      "url": "https://your-server.com/mcp",
      "transport": "streamable-http"
    }
  }
}
```

## 技术细节

- **数据源**：baostock（免费 A 股日线数据）
- **股票池**：沪深 300 / 中证 500 / 中证 1000 / 全 A
- **回测方法**：分位数分组回测（非事件驱动）
- **指标体系**：Sharpe、Sortino、IC、IR、单调性、换手率等 20+ 指标
- **报告**：QuantStats HTML 交互式报告

## 总结

MCP 让 AI 从"只会聊天"变成"能干活"。QuantGPT 是一个很好的例子——把量化回测能力封装成 MCP 工具，Claude 就变成了一个懂量化的研究助手。

你不需要写 Python 代码，不需要调 API，只要用自然语言描述你的因子想法，剩下的交给 Claude + QuantGPT。

---

*QuantGPT 开源免费，欢迎 Star: [GitHub 仓库链接]*
*在线体验（免登录）: [quantgpt.com]*
