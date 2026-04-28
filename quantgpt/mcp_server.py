"""FastMCP server for factor backtesting.

Provides tools for Agent-driven backtest workflow:
- list_operators: Show available factor expression operators
- list_universes: Show available stock universes
- validate_expression: Check expression syntax
- run_backtest: Execute full backtest pipeline
- score_factor: Compute composite factor quality score
- diagnose_factor: Diagnose factor issues and suggest mutations
- run_anti_overfit: Run anti-overfit detection
- run_rolling_validation: Walk-forward rolling validation
"""

import json
import logging
import time
import traceback

import pandas as pd
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .expression_parser import ExpressionParser, parse_expression
from .expression_parser import __doc__ as _expr_module_doc
from .market_data import MarketDataFetcher, get_universe, fetch_benchmark_returns, UNIVERSES, BENCHMARK_CODES
from .backtest import run_factor_backtest, api_context
from .report import generate_report
from .fundamental_data import ALL_FUNDAMENTAL_NAMES
from .mcp_tracking import track_mcp_result

import sys
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "quantgpt",
    instructions="QuantGPT — A 股因子回测服务。先用 list_operators 了解可用算子，再用 run_backtest 执行回测。可用 score_factor 评分、diagnose_factor 诊断、run_anti_overfit 检测过拟合、run_rolling_validation 滚动验证。",
    streamable_http_path="/",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=["quantgpt.online", "www.quantgpt.online", "localhost", "127.0.0.1"],
    ),
)


def _enrich_with_fundamentals(expression: str, market_df, stock_codes: list, start_date: str, end_date: str):
    """Conditionally fetch and merge fundamental data if the expression uses fundamental vars.

    Uses rqdatac get_factor (daily frequency) as primary source, baostock quarterly as fallback.
    """
    from .fundamental_data import detect_fundamental_vars, FundamentalDataFetcher, enrich_with_fundamentals_rq
    fund_vars = detect_fundamental_vars(expression)
    if not fund_vars:
        return market_df
    logger.info(f"Detected fundamental vars: {fund_vars}, fetching financial data...")

    # Try rqdatac first (returns daily-frequency data, no alignment needed)
    rq_result = enrich_with_fundamentals_rq(market_df, fund_vars, stock_codes, start_date, end_date)
    if rq_result is not None:
        return rq_result

    # Fallback: baostock quarterly + align_to_daily
    logger.info("rqdatac unavailable, falling back to baostock for fundamentals...")
    fetcher = FundamentalDataFetcher()
    # Quarterly financial data (non-dividend vars)
    non_div_vars = fund_vars - {"dividend_yield"}
    if non_div_vars:
        qdf = fetcher.fetch_fundamentals(stock_codes, start_date, end_date, non_div_vars)
        if qdf is not None and len(qdf) > 0:
            market_df = fetcher.align_to_daily(qdf, market_df, non_div_vars)
            logger.info(f"Fundamental data merged, columns: {list(market_df.columns)}")
        else:
            logger.warning("No fundamental data fetched, fundamental vars will be NaN")
    # Dividend data
    if "dividend_yield" in fund_vars:
        div_df = fetcher.fetch_dividend_data(stock_codes, start_date, end_date)
        if div_df is not None and len(div_df) > 0:
            market_df = fetcher.align_dividends_to_daily(div_df, market_df)
            logger.info("Dividend data merged")
        else:
            logger.warning("No dividend data fetched, dividend_yield will be NaN")
    return market_df


def _fetch_data_for_market(universe: str, start_date: str, end_date: str):
    """Fetch market data and stock codes. Returns (market_df, stock_codes)."""
    stock_codes = get_universe(universe, date=start_date)
    fetcher = MarketDataFetcher()
    market_df = fetcher.fetch_stocks(stock_codes, start_date, end_date)
    return market_df, stock_codes


def _fetch_benchmark_for_market(benchmark: str, start_date: str, end_date: str):
    """Fetch benchmark returns."""
    return fetch_benchmark_returns(benchmark, start_date, end_date)


# Dummy DataFrame for expression validation (includes fundamental columns)
_VALIDATION_DUMMY = pd.DataFrame({
    "open": [1.0, 2.0, 3.0], "high": [1.1, 2.1, 3.1],
    "low": [0.9, 1.9, 2.9], "close": [1.0, 2.0, 3.0],
    "volume": [100, 200, 300], "amount": [100, 400, 900],
    "pct_change": [0, 100, 50],
    "trade_date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    **{name: [1.0, 1.1, 1.2] for name in ALL_FUNDAMENTAL_NAMES},
})


@mcp.tool()
def list_operators() -> str:
    """返回因子表达式支持的全部操作符及用法说明。Agent 据此生成因子表达式。"""
    return _expr_module_doc or _OPERATORS_DOC


@mcp.tool()
def list_universes() -> str:
    """返回可用股票池列表及说明。"""
    a_share_info = {
        "small_scale": f"5 只蓝筹股（快速测试）: {UNIVERSES['small_scale']}",
        "hs300": "沪深300成分股（动态获取）",
        "csi500": "中证500成分股（动态获取）",
        "csi1000": "中证1000成分股（派生: 全A - HS300 - CSI500, 取前1000）",
        "csi2000": "中证2000成分股（派生: 全A - HS300 - CSI500 - CSI1000, 取前2000）",
    }
    a_share_benchmarks = {k: v["name"] for k, v in BENCHMARK_CODES.items()}
    return json.dumps({
        "universes": a_share_info,
        "benchmarks": a_share_benchmarks,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def validate_expression(expression: str) -> str:
    """验证因子表达式语法是否正确。返回 OK 或错误信息。"""
    import pandas as pd

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
        func(_VALIDATION_DUMMY)
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
    neutralize_industry: bool = True,
    neutralize_cap: bool = True,
) -> str:
    """执行因子回测,生成 QuantStats HTML 报告。

    Args:
        expression: 因子表达式,如 "rank(close/ts_mean(close, 20))"
        universe: 股票池名称 (small_scale/hs300/csi500/csi1000/csi2000)
        start_date: 回测起始日期 YYYY-MM-DD
        end_date: 回测结束日期 YYYY-MM-DD
        n_groups: 分组数量
        holding_period: 持仓周期(交易日)
        benchmark: 基准 (hs300/zz500/sz50/csi1000)
        neutralize_industry: 行业中性化(默认开启)
        neutralize_cap: 市值中性化(默认开启)

    Returns:
        JSON string with report_path, metrics, group_returns, anti_overfit.
    """
    _start = time.monotonic()
    _error_msg = None
    _result_str = None
    try:
        logger.info(f"Getting universe: {universe}")
        market_df, stock_codes = _fetch_data_for_market(universe, start_date, end_date)
        if market_df is None or len(market_df) == 0:
            return json.dumps({"error": "No market data available. Check date range and stock codes."})

        market_df = _enrich_with_fundamentals(expression, market_df, stock_codes, start_date, end_date)

        logger.info(f"Running backtest: {expression}")
        with api_context():
            result = run_factor_backtest(market_df, expression, n_groups, holding_period,
                                         neutralize_industry=neutralize_industry,
                                         neutralize_cap=neutralize_cap)

        # Anti-overfit analysis
        anti_overfit_result = None
        factor_df = result.get("_factor_df")
        if factor_df is not None and len(factor_df) > 100:
            try:
                from .anti_overfit import run_anti_overfit as _run_ao
                anti_overfit_result = _run_ao(factor_df, holding_period)
            except Exception as e:
                logger.warning(f"Anti-overfit analysis failed: {e}")

        bm_returns = None
        try:
            bm_returns = _fetch_benchmark_for_market(benchmark, start_date, end_date)
        except Exception as e:
            logger.warning(f"Benchmark fetch failed: {e}")

        report_result = generate_report(
            result["ls_returns"],
            benchmark_returns=bm_returns,
            title=f"Factor: {expression}",
        )

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
                "wq_fitness": result.get("wq_fitness", 0),
                "cost_adjusted": result.get("cost_adjusted", False),
                "cost_rate": result.get("cost_rate", 0),
                "total_cost_drag": result.get("total_cost_drag", 0),
            },
            "wq_brain": result.get("wq_brain", {}),
            "anti_overfit": anti_overfit_result,
            "params": {
                "expression": expression,
                "universe": universe,
                "start_date": start_date,
                "end_date": end_date,
                "n_groups": n_groups,
                "holding_period": holding_period,
                "benchmark": benchmark,
                "neutralize_industry": neutralize_industry,
                "neutralize_cap": neutralize_cap,
                "stock_count": len(stock_codes),
            },
        }
        _result_str = json.dumps(output, ensure_ascii=False, indent=2, default=str)
        return _result_str

    except Exception as e:
        logger.error(f"Backtest failed: {traceback.format_exc()}")
        _error_msg = str(e)
        _result_str = json.dumps({"error": str(e)})
        return _result_str
    finally:
        track_mcp_result("mcp_backtest", expression,
                         {"universe": universe, "start_date": start_date, "end_date": end_date,
                          "n_groups": n_groups, "holding_period": holding_period, "benchmark": benchmark},
                         _result_str, _error_msg, time.monotonic() - _start)


@mcp.tool()
def score_factor(
    expression: str,
    universe: str = "hs300",
    start_date: str = "2023-01-01",
    end_date: str = "2025-12-31",
    n_groups: int = 5,
    holding_period: int = 5,
    benchmark: str = "hs300",
    neutralize_industry: bool = True,
    neutralize_cap: bool = True,
) -> str:
    """执行因子回测并返回综合评分(0-100)和等级(A/B/C/D)。

    比 run_backtest 更轻量,不生成 HTML 报告,专注评分。

    Args:
        expression: 因子表达式
        universe: 股票池 (small_scale/hs300/csi500/csi1000/csi2000)
        start_date: 起始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        n_groups: 分组数量
        holding_period: 持仓周期(交易日)
        benchmark: 基准 (hs300/zz500/sz50/csi1000)
        neutralize_industry: 行业中性化(默认开启)
        neutralize_cap: 市值中性化(默认开启)

    Returns:
        JSON with score, grade, component_scores, key metrics.
    """
    from .iteration import compute_factor_score

    _start = time.monotonic()
    _error_msg = None
    _result_str = None
    try:
        market_df, stock_codes = _fetch_data_for_market(universe, start_date, end_date)
        if market_df is None or len(market_df) == 0:
            return json.dumps({"error": "No market data available."})

        market_df = _enrich_with_fundamentals(expression, market_df, stock_codes, start_date, end_date)

        with api_context():
            result = run_factor_backtest(market_df, expression, n_groups, holding_period,
                                         neutralize_industry=neutralize_industry,
                                         neutralize_cap=neutralize_cap)

        bm_returns = None
        try:
            bm_returns = _fetch_benchmark_for_market(benchmark, start_date, end_date)
        except Exception:
            pass

        report_result = generate_report(
            result["strategy_returns"],
            benchmark_returns=bm_returns,
            title="Factor Score",
        )

        scoring = compute_factor_score(
            backtest_summary={
                "long_short_sharpe": result["long_short_sharpe"],
                "monotonicity_score": result["monotonicity_score"],
                "spread": result["spread"],
                "ic_mean": result.get("ic_mean", 0),
                "rank_ic_mean": result.get("rank_ic_mean", 0),
                "ic_ir": result.get("ic_ir", 0),
                "ic_win_rate": result.get("ic_win_rate", 0),
            },
            report_metrics=report_result["metrics"],
        )

        output = {
            "score": scoring["score"],
            "grade": scoring["grade"],
            "component_scores": scoring["component_scores"],
            "key_metrics": {
                "ic_mean": result.get("ic_mean", 0),
                "ic_ir": result.get("ic_ir", 0),
                "monotonicity": result["monotonicity_score"],
                "top_group_sharpe": result.get("top_group_sharpe", 0),
                "turnover": result.get("turnover", 0),
                "wq_fitness": result.get("wq_fitness", 0),
                "sharpe": report_result["metrics"].get("sharpe", 0),
                "max_drawdown": report_result["metrics"].get("max_drawdown", 0),
            },
        }
        _result_str = json.dumps(output, ensure_ascii=False, indent=2, default=str)
        return _result_str

    except Exception as e:
        logger.error(f"Score failed: {traceback.format_exc()}")
        _error_msg = str(e)
        _result_str = json.dumps({"error": str(e)})
        return _result_str
    finally:
        track_mcp_result("mcp_score", expression,
                         {"universe": universe, "start_date": start_date, "end_date": end_date,
                          "n_groups": n_groups, "holding_period": holding_period, "benchmark": benchmark},
                         _result_str, _error_msg, time.monotonic() - _start)


@mcp.tool()
def diagnose_factor(
    expression: str,
    ic_mean: float = 0.0,
    ic_ir: float = 0.0,
    monotonicity_score: float = 0.0,
    score: float = 50.0,
) -> str:
    """诊断因子问题并推荐突变策略。

    根据因子的 IC/IR/单调性/评分,判断失败模式(IC为零、IC为负、嵌套过深等),
    返回推荐的改进策略和定向 LLM 提示词。

    Args:
        expression: 当前因子表达式
        ic_mean: IC 均值
        ic_ir: IC 信息比率
        monotonicity_score: 分组单调性 (0-1)
        score: 综合评分 (0-100)

    Returns:
        JSON with diagnosis strategy, reason, and suggested mutation prompt.
    """
    from .mutation_engine import MutationEngine

    try:
        engine = MutationEngine(
            expression=expression,
            metrics={
                "backtest_summary": {
                    "ic_mean": ic_mean,
                    "ic_ir": ic_ir,
                    "monotonicity_score": monotonicity_score,
                },
                "report_metrics": {},
            },
            score=score,
        )
        diagnosis = engine.diagnose_failure()
        sys_prompt, user_prompt = engine.build_mutation_prompt()

        output = {
            "strategy": diagnosis.strategy.value,
            "reason": diagnosis.reason,
            "details": diagnosis.details,
            "mutation_prompt": {
                "system": sys_prompt[:500] + "..." if len(sys_prompt) > 500 else sys_prompt,
                "user": user_prompt,
            },
        }
        return json.dumps(output, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Diagnose failed: {traceback.format_exc()}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def run_anti_overfit(
    expression: str,
    universe: str = "hs300",
    start_date: str = "2023-01-01",
    end_date: str = "2025-12-31",
    holding_period: int = 5,
    neutralize_industry: bool = True,
    neutralize_cap: bool = True,
) -> str:
    """对因子执行反过拟合检测(4项测试)。

    测试项: IC稳定性、子样本压力、安慰剂检验、半衰期估计。
    返回总分(0-100)和各测试通过情况。

    Args:
        expression: 因子表达式
        universe: 股票池 (small_scale/hs300/csi500/csi1000/csi2000)
        start_date: 起始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        holding_period: 持仓周期(交易日)
        neutralize_industry: 行业中性化(默认开启)
        neutralize_cap: 市值中性化(默认开启)

    Returns:
        JSON with score, recommendation, and per-test details.
    """
    from .anti_overfit import run_anti_overfit as _run_ao

    _start = time.monotonic()
    _error_msg = None
    _result_str = None
    try:
        market_df, stock_codes = _fetch_data_for_market(universe, start_date, end_date)
        if market_df is None or len(market_df) == 0:
            return json.dumps({"error": "No market data available."})

        market_df = _enrich_with_fundamentals(expression, market_df, stock_codes, start_date, end_date)

        with api_context():
            result = run_factor_backtest(market_df, expression, holding_period=holding_period, cost_rate=0,
                                         neutralize_industry=neutralize_industry,
                                         neutralize_cap=neutralize_cap)
        factor_df = result.get("_factor_df")
        if factor_df is None or len(factor_df) < 100:
            return json.dumps({"error": "Insufficient factor data for anti-overfit analysis."})

        ao_result = _run_ao(factor_df, holding_period)
        _result_str = json.dumps(ao_result, ensure_ascii=False, indent=2, default=str)
        return _result_str

    except Exception as e:
        logger.error(f"Anti-overfit failed: {traceback.format_exc()}")
        _error_msg = str(e)
        _result_str = json.dumps({"error": str(e)})
        return _result_str
    finally:
        track_mcp_result("mcp_antioverfit", expression,
                         {"universe": universe, "start_date": start_date, "end_date": end_date,
                          "holding_period": holding_period},
                         _result_str, _error_msg, time.monotonic() - _start)


@mcp.tool()
def run_rolling_validation(
    expression: str,
    universe: str = "hs300",
    start_date: str = "2020-01-01",
    end_date: str = "2025-12-31",
    holding_period: int = 5,
    neutralize_industry: bool = True,
    neutralize_cap: bool = True,
) -> str:
    """对因子执行滚动验证(Walk-Forward)。

    将数据切分为多个 训练/验证/测试 窗口(默认 3年/1年/1年,步长3个月),
    计算每个窗口的 IC/IR,评估因子在样本外的衰减情况。

    Args:
        expression: 因子表达式
        universe: 股票池 (small_scale/hs300/csi500/csi1000/csi2000)
        start_date: 起始日期(建议≥5年数据)
        end_date: 结束日期
        holding_period: 持仓周期(交易日)
        neutralize_industry: 行业中性化(默认开启)
        neutralize_cap: 市值中性化(默认开启)

    Returns:
        JSON with composite score, per-window results, decay analysis.
    """
    from .rolling_validator import run_rolling_validation as _run_rv

    _start = time.monotonic()
    _error_msg = None
    _result_str = None
    try:
        market_df, stock_codes = _fetch_data_for_market(universe, start_date, end_date)
        if market_df is None or len(market_df) == 0:
            return json.dumps({"error": "No market data available."})

        market_df = _enrich_with_fundamentals(expression, market_df, stock_codes, start_date, end_date)

        with api_context():
            result = run_factor_backtest(market_df, expression, holding_period=holding_period, cost_rate=0,
                                         neutralize_industry=neutralize_industry,
                                         neutralize_cap=neutralize_cap)
        factor_df = result.get("_factor_df")
        if factor_df is None or len(factor_df) < 100:
            return json.dumps({"error": "Insufficient factor data for rolling validation."})

        rv_result = _run_rv(factor_df, holding_period)
        _result_str = json.dumps(rv_result, ensure_ascii=False, indent=2, default=str)
        return _result_str

    except Exception as e:
        logger.error(f"Rolling validation failed: {traceback.format_exc()}")
        _error_msg = str(e)
        _result_str = json.dumps({"error": str(e)})
        return _result_str
    finally:
        track_mcp_result("mcp_rolling", expression,
                         {"universe": universe, "start_date": start_date, "end_date": end_date,
                          "holding_period": holding_period},
                         _result_str, _error_msg, time.monotonic() - _start)


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
