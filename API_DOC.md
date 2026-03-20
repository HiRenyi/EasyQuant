# QuantGPT API 文档

## 启动服务

```bash
cd /path/to/simple-backtest
pip install -e .

DEEPSEEK_API_KEY=sk-xxx python -m quantgpt --transport http --host 0.0.0.0 --port 8000
```

启动后：
- API 地址：`http://host:8000/api/v1/`
- Swagger 文档：`http://host:8000/docs`

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DEEPSEEK_API_KEY` | 是 | — | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com/v1` | API 地址（兼容 OpenAI 接口的均可） |
| `DEEPSEEK_MODEL` | 否 | `deepseek-chat` | 模型名称 |

## 数据预热

大股票池首次下载耗时较长，建议提前缓存：

```bash
python -m quantgpt --prefetch hs300 csi500
```

---

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auto_backtest` | 提交回测任务（异步，立即返回 task_id） |
| GET | `/api/v1/tasks/{task_id}` | 查询任务状态和结果 |
| GET | `/api/v1/reports/{filename}` | 下载 HTML 报告 |

---

### POST /api/v1/auto_backtest

提交回测任务，立即返回 `task_id`，后台异步执行 LLM 生成表达式 + 回测 + 报告生成。

```bash
curl -X POST http://localhost:8000/api/v1/auto_backtest \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "帮我测试一个20日动量因子",
    "universe": "small_scale",
    "start_date": "2023-01-01",
    "end_date": "2024-12-31"
  }'
```

请求体：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `prompt` | string | 是 | — | 自然语言描述 |
| `universe` | string | 否 | `hs300` | 股票池：`small_scale` / `hs300` / `csi500` |
| `start_date` | string | 否 | `2022-01-01` | 起始日期 YYYY-MM-DD |
| `end_date` | string | 否 | `2024-12-31` | 结束日期 YYYY-MM-DD |
| `n_groups` | int | 否 | `5` | 分组数量 (2~20) |
| `holding_period` | int | 否 | `5` | 持仓周期，交易日 (1~60) |
| `benchmark` | string | 否 | `hs300` | 基准指数：`hs300` / `zz500` / `sz50` |

响应（HTTP 202）：

```json
{
  "task_id": "a1b2c3d4e5f6",
  "status": "pending"
}
```

---

### GET /api/v1/tasks/{task_id}

轮询任务状态。`status` 流转：`pending` → `generating_expression` → `validating` → `fetching_data` → `backtesting` → `generating_report` → `completed` / `failed`

```bash
curl http://localhost:8000/api/v1/tasks/a1b2c3d4e5f6
```

进行中响应：

```json
{
  "task_id": "a1b2c3d4e5f6",
  "status": "backtesting",
  "params": { "prompt": "帮我测试一个20日动量因子", "..." : "..." },
  "expression": "rank(close/ts_mean(close, 20))"
}
```

完成响应：

```json
{
  "task_id": "a1b2c3d4e5f6",
  "status": "completed",
  "params": { "..." : "..." },
  "expression": "rank(close/ts_mean(close, 20))",
  "result": {
    "report_url": "/api/v1/reports/backtest_report_20260319_130818.html",
    "report_path": "/absolute/path/to/report.html",
    "metrics": {
      "total_return": -0.644,
      "cagr": -0.419,
      "sharpe": -0.674,
      "sortino": -0.875,
      "max_drawdown": -0.895,
      "volatility": 0.587,
      "win_rate": 0.507,
      "profit_factor": 0.902
    },
    "backtest_summary": {
      "long_short_sharpe": -0.279,
      "monotonicity_score": 0.6,
      "spread": -0.00145,
      "group_returns": {
        "0": { "mean_return": 0.00386, "sharpe": 0.639 },
        "4": { "mean_return": 0.00241, "sharpe": 0.475 }
      }
    },
    "params": {
      "expression": "rank(close/ts_mean(close, 20))",
      "universe": "small_scale",
      "start_date": "2023-01-01",
      "end_date": "2024-12-31",
      "n_groups": 5,
      "holding_period": 5,
      "benchmark": "hs300",
      "stock_count": 5
    },
    "llm": {
      "prompt": "帮我测试一个20日动量因子",
      "generated_expression": "rank(close/ts_mean(close, 20))"
    }
  }
}
```

失败响应：

```json
{
  "task_id": "a1b2c3d4e5f6",
  "status": "failed",
  "error": "No market data available."
}
```

---

### GET /api/v1/reports/{filename}

下载 HTML 报告。`filename` 从任务结果的 `result.report_url` 中获取。

```bash
# 浏览器直接访问
http://localhost:8000/api/v1/reports/backtest_report_20260319_130818.html

# 或 curl 下载
curl -O http://localhost:8000/api/v1/reports/backtest_report_20260319_130818.html
```

---

## 典型调用流程

```bash
# 1. 提交任务
TASK_ID=$(curl -s -X POST http://localhost:8000/api/v1/auto_backtest \
  -H "Content-Type: application/json" \
  -d '{"prompt": "20日动量因子", "universe": "small_scale"}' | jq -r '.task_id')

# 2. 轮询状态（每 5 秒）
while true; do
  STATUS=$(curl -s http://localhost:8000/api/v1/tasks/$TASK_ID | jq -r '.status')
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] && break
  sleep 5
done

# 3. 获取结果
curl -s http://localhost:8000/api/v1/tasks/$TASK_ID | jq '.result'
```

---

## 股票池

| 名称 | 说明 |
|------|------|
| `small_scale` | 5 只蓝筹（茅台、平安、五粮液、美的、招行），快速测试用 |
| `hs300` | 沪深300成分股，动态获取 |
| `csi500` | 中证500成分股，动态获取 |

首次使用 `hs300`/`csi500` 会从 baostock 下载数据，后续读缓存。
