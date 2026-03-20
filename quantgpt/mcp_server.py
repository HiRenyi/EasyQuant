"""FastMCP server for factor backtesting.

Provides 4 tools for Agent-driven backtest workflow:
- list_operators: Show available factor expression operators
- list_universes: Show available stock universes
- validate_expression: Check expression syntax
- run_backtest: Execute full backtest pipeline
"""

import json
import logging
import traceback

from mcp.server.fastmcp import FastMCP

from .expression_parser import ExpressionParser, parse_expression
from .expression_parser import __doc__ as _expr_module_doc
from .market_data import MarketDataFetcher, get_universe, fetch_benchmark_returns, UNIVERSES, BENCHMARK_CODES
from .backtest import run_factor_backtest
from .report import generate_report

import sys
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

mcp = FastMCP("quantgpt", instructions="QuantGPT — A 股因子回测服务。先用 list_operators 了解可用算子，再用 run_backtest 执行回测。")


@mcp.tool()
def list_operators() -> str:
    """返回因子表达式支持的全部操作符及用法说明。Agent 据此生成因子表达式。"""
    return _expr_module_doc or _OPERATORS_DOC


@mcp.tool()
def list_universes() -> str:
    """返回可用股票池列表及说明。"""
    info = {
        "small_scale": f"5 只蓝筹股（快速测试）: {UNIVERSES['small_scale']}",
        "hs300": "沪深300成分股（动态获取）",
        "csi500": "中证500成分股（动态获取）",
    }
    benchmarks = {k: v["name"] for k, v in BENCHMARK_CODES.items()}
    return json.dumps({"universes": info, "benchmarks": benchmarks}, ensure_ascii=False, indent=2)


@mcp.tool()
def validate_expression(expression: str) -> str:
    """验证因子表达式语法是否正确。返回 OK 或错误信息。"""
    import pandas as pd
    import numpy as np

    # Parentheses balance pre-check
    depth = 0
    for i, ch in enumerate(expression):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth < 0:
                return f"ERROR: 括号不平衡：位置 {i} 处多余的右括号 ')'"
    if depth > 0:
        return f"ERROR: 括号不平衡：缺少 {depth} 个右括号 ')'"

    try:
        func = parse_expression(expression)
        # Quick smoke test on a tiny dummy DataFrame
        dummy = pd.DataFrame({
            "open": [1.0, 2.0, 3.0],
            "high": [1.1, 2.1, 3.1],
            "low": [0.9, 1.9, 2.9],
            "close": [1.0, 2.0, 3.0],
            "volume": [100, 200, 300],
            "amount": [100, 400, 900],
            "pct_change": [0, 100, 50],
        })
        func(dummy)
        return "OK: expression is valid"
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def run_backtest(
    expression: str,
    universe: str = "hs300",
    start_date: str = "2023-01-01",
    end_date: str = "2025-12-31",
    n_groups: int = 5,
    holding_period: int = 5,
    benchmark: str = "hs300",
) -> str:
    """执行因子回测，生成 QuantStats HTML 报告。

    Args:
        expression: 因子表达式，如 "rank(close/ts_mean(close, 20))"
        universe: 股票池名称 (small_scale / hs300 / csi500)
        start_date: 回测起始日期 YYYY-MM-DD
        end_date: 回测结束日期 YYYY-MM-DD
        n_groups: 分组数量
        holding_period: 持仓周期（交易日）
        benchmark: 基准指数 (hs300 / zz500 / sz50)

    Returns:
        JSON string with report_path, metrics, group_returns.
    """
    try:
        # 1. Get stock universe
        logger.info(f"Getting universe: {universe}")
        stock_codes = get_universe(universe, date=start_date)
        logger.info(f"Universe {universe}: {len(stock_codes)} stocks")

        # 2. Fetch market data
        fetcher = MarketDataFetcher()
        market_df = fetcher.fetch_stocks(stock_codes, start_date, end_date)
        if market_df is None or len(market_df) == 0:
            return json.dumps({"error": "No market data available. Check date range and stock codes."})

        # 3. Run backtest
        logger.info(f"Running backtest: {expression}")
        result = run_factor_backtest(market_df, expression, n_groups, holding_period)

        # 3a. Anti-overfit analysis
        anti_overfit_result = None
        factor_df = result.get("_factor_df")
        if factor_df is not None and len(factor_df) > 100:
            try:
                from .anti_overfit import run_anti_overfit
                anti_overfit_result = run_anti_overfit(factor_df, holding_period)
            except Exception as e:
                logger.warning(f"Anti-overfit analysis failed: {e}")

        # 4. Fetch benchmark & generate report
        bm_returns = None
        try:
            bm_returns = fetch_benchmark_returns(benchmark, start_date, end_date)
        except Exception as e:
            logger.warning(f"Benchmark fetch failed: {e}")

        report_result = generate_report(
            result["ls_returns"],
            benchmark_returns=bm_returns,
            title=f"Factor: {expression}",
        )

        # 5. Build response
        output = {
            "report_path": report_result["report_path"],
            "metrics": report_result["metrics"],
            "backtest_summary": {
                "long_short_sharpe": result["long_short_sharpe"],
                "long_short_annual": result.get("long_short_annual", 0),
                "top_group_sharpe": result.get("top_group_sharpe", 0),
                "monotonicity_score": result["monotonicity_score"],
                "spread": result["spread"],
                "group_returns": result["group_returns"],
                "ic_mean": result.get("ic_mean", 0),
                "rank_ic_mean": result.get("rank_ic_mean", 0),
                "ic_ir": result.get("ic_ir", 0),
                "ic_win_rate": result.get("ic_win_rate", 0),
                "turnover": result.get("turnover", 0),
                "cost_adjusted": result.get("cost_adjusted", False),
                "cost_rate": result.get("cost_rate", 0),
                "total_cost_drag": result.get("total_cost_drag", 0),
            },
            "anti_overfit": anti_overfit_result,
            "params": {
                "expression": expression,
                "universe": universe,
                "start_date": start_date,
                "end_date": end_date,
                "n_groups": n_groups,
                "holding_period": holding_period,
                "benchmark": benchmark,
                "stock_count": len(stock_codes),
            },
        }
        return json.dumps(output, ensure_ascii=False, indent=2, default=str)

    except Exception as e:
        logger.error(f"Backtest failed: {traceback.format_exc()}")
        return json.dumps({"error": str(e)})


# Operator documentation fallback
_OPERATORS_DOC = """
因子表达式操作符:

一元函数: rank, zscore, sign, log, abs, scale, tanh, sigmoid, exp, sqrt
时序函数: ts_mean, ts_std, ts_max, ts_min, ts_sum, ts_shift, ts_delta, ts_rank, ts_argmax, ts_argmin, decay_linear, product
  用法: ts_mean(close, 20) — 20日均值
双列时序: ts_corr(col1, col2, N), ts_cov(col1, col2, N)
二元函数: power, max, min
条件函数: clip(expr, lo, hi), where(cond, true_val, false_val)
算术运算: +, -, *, /, ^
比较运算: >, <, >=, <=, ==, !=
特殊变量: vwap, returns, adv{N} (如 adv20)
可用列名: open, high, low, close, volume, amount, pct_change
别名: delta=ts_delta, delay=ts_shift, correlation=ts_corr, covariance=ts_cov
"""
