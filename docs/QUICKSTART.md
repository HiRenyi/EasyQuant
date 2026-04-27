# Quick Start — 5 分钟跑通第一个因子回测

## Prerequisites

- Python 3.10+
- Node.js 20+ (optional, for frontend)

## 1. Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/quantgpt.git
cd quantgpt
make setup
```

This creates a virtual environment, installs all dependencies, and generates `.env` from the template.

**No API keys needed** for expression-only mode.

## 2. Start the Server

```bash
make run
```

The server starts at `http://localhost:8002`. Open it in your browser.

## 3. Run Your First Backtest

In the web UI, enter a factor expression directly:

```
rank(close / ts_mean(close, 20))
```

This is a 20-day momentum factor — it ranks stocks by how far their current price deviates from the 20-day moving average.

Click "开始回测" and wait for results. You'll see:
- Equity curve and drawdown chart
- Group returns (quantile performance)
- IC/IR metrics
- Anti-overfit analysis
- QuantStats HTML report

## 4. Try More Expressions

```
# Price-volume divergence (the validated WQ BRAIN factor)
-1 * rank(ts_corr(close, volume, 5))

# Volume anomaly
rank(volume / ts_mean(volume, 10))

# Multi-signal composite
rank(ts_corr(close, volume, 20)) * rank(ts_delta(close, 10) / close)

# Value factor (needs fundamental data)
rank(-1 * pe)
```

## 5. Enable Natural Language Mode (Optional)

To describe factors in Chinese instead of writing expressions:

1. Get a DeepSeek API key from [platform.deepseek.com](https://platform.deepseek.com)
2. Edit `.env`:
   ```
   DEEPSEEK_API_KEY=sk-your-key-here
   ```
3. Restart the server: `make run`
4. Now you can type: `"找一个基于价量背离的短期反转因子"`

## 6. Build the Frontend (Optional)

For the full web experience with Vite optimized build:

```bash
make frontend   # builds frontend/dist
make run        # serves both API and SPA
```

## 7. Use via API

```bash
# Direct expression backtest
curl -X POST http://localhost:8002/api/v1/auto_backtest \
  -H "Content-Type: application/json" \
  -d '{"prompt": "rank(close/ts_mean(close,20))", "universe": "small_scale"}'

# Check task status
curl http://localhost:8002/api/v1/tasks/{task_id}
```

## 8. Use via MCP (for Claude Code / AI Agents)

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "quantgpt": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "quantgpt"],
      "cwd": "/path/to/quantgpt"
    }
  }
}
```

Then in Claude Code:
```
Use the score_factor tool to evaluate: rank(ts_corr(close, volume, 10))
```

## What's Next

- Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system design
- Check [MCP_GUIDE.md](MCP_GUIDE.md) for AI agent integration
- Try the `/factor-mine` skill for AI-driven factor research
- Browse `example_factor/` for validated factor results
