"""Factor iteration optimization — scoring, prompt building, candidate generation.

Migrated and simplified from XTQuant/ai-quant-research-execution/experiments/case60.
"""

import hashlib
import logging
import os
import re
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

from .backtest import run_factor_backtest
from .expression_parser import parse_expression
from .mutation_engine import MutationEngine
from .report import generate_report

logger = logging.getLogger(__name__)


# ---- Factor scoring ----

def compute_factor_score(backtest_summary: dict, report_metrics: dict, anti_overfit_score: float | None = None) -> dict:
    """Compute a composite 0-100 score for a factor backtest result.

    Weights (without anti_overfit):
        Sharpe 25%, monotonicity 20%, spread 15%, CAGR 15%, max_drawdown 15%, win_rate 10%
    Weights (with anti_overfit):
        Sharpe 22.5%, monotonicity 18%, spread 13.5%, CAGR 13.5%, max_drawdown 13.5%, win_rate 9%, anti_overfit 10%
    """

    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    sharpe = report_metrics.get("sharpe", 0.0)
    cagr = report_metrics.get("cagr", 0.0)
    max_dd = report_metrics.get("max_drawdown", 0.0)  # negative
    win_rate = report_metrics.get("win_rate", 0.0)
    mono = backtest_summary.get("monotonicity_score", 0.0)
    spread = backtest_summary.get("spread", 0.0)

    # Sharpe: clamp [-1, 3] -> 0-100
    sharpe_score = (_clamp(sharpe, -1, 3) + 1) / 4 * 100

    # Monotonicity: already 0-1 -> 0-100
    mono_score = _clamp(mono, 0, 1) * 100

    # Spread: clamp [-0.05, 0.05], 0 -> 50
    spread_score = (_clamp(spread, -0.05, 0.05) + 0.05) / 0.10 * 100

    # CAGR: clamp [-0.3, 0.5], 0 -> 37.5
    cagr_score = (_clamp(cagr, -0.3, 0.5) + 0.3) / 0.8 * 100

    # Max drawdown: 0% -> 100, -50% -> 0 (max_dd is negative)
    dd_val = _clamp(max_dd, -0.5, 0.0)
    dd_score = (dd_val + 0.5) / 0.5 * 100

    # Win rate: 0.3 -> 0, 0.5 -> 50, 0.7 -> 100
    wr_score = (_clamp(win_rate, 0.3, 0.7) - 0.3) / 0.4 * 100

    components = {
        "sharpe": round(sharpe_score, 1),
        "monotonicity": round(mono_score, 1),
        "spread": round(spread_score, 1),
        "cagr": round(cagr_score, 1),
        "max_drawdown": round(dd_score, 1),
        "win_rate": round(wr_score, 1),
    }

    if anti_overfit_score is not None:
        ao_clamped = _clamp(anti_overfit_score, 0, 100)
        components["anti_overfit"] = round(ao_clamped, 1)
        # Re-weight: reduce each original weight by 10% proportionally, add 10% for anti_overfit
        score = (
            sharpe_score * 0.225
            + mono_score * 0.18
            + spread_score * 0.135
            + cagr_score * 0.135
            + dd_score * 0.135
            + wr_score * 0.09
            + ao_clamped * 0.10
        )
    else:
        score = (
            sharpe_score * 0.25
            + mono_score * 0.20
            + spread_score * 0.15
            + cagr_score * 0.15
            + dd_score * 0.15
            + wr_score * 0.10
        )
    score = round(_clamp(score, 0, 100), 1)

    if score >= 80:
        grade = "A"
    elif score >= 60:
        grade = "B"
    elif score >= 40:
        grade = "C"
    else:
        grade = "D"

    return {"score": score, "grade": grade, "component_scores": components}


# ---- Iterate prompt building ----

_FACTOR_CATEGORIES = [
    ("Momentum", "rank(ts_delta(close, 20) / ts_shift(close, 20))"),
    ("Reversal", "rank(-1 * ts_delta(close, 5) / ts_shift(close, 5))"),
    ("Volatility", "rank(ts_std(returns, 20))"),
    ("Volume", "rank(volume / ts_mean(volume, 20))"),
    ("Value", "rank((close - ts_min(close, 60)) / (ts_max(close, 60) - ts_min(close, 60) + 1e-8))"),
    ("Correlation", "rank(ts_corr(close, volume, 20))"),
    ("MeanReversion", "rank((close - ts_mean(close, 20)) / (ts_std(close, 20) + 1e-8))"),
    ("Intraday", "rank((close - open) / (high - low + 1e-8))"),
    ("NonlinearMomentum", "sign_power(ts_delta(close, 20) / close, 0.5) * rank(volume / adv20)"),
    ("DecayWeighted", "decay_linear(rank(ts_corr(vwap, volume, 10)), 5)"),
    ("Interaction", "rank(ts_corr(close, volume, 20)) * rank(ts_delta(close, 10) / close)"),
    ("Conditional", "rank(where(ts_rank(volume, 20) > 0.7, ts_delta(close, 10) / close, 0))"),
]

_DIVERSITY_GUIDE = """
## 多样性与非线性原则
1. 🚨 只能使用 SUPPORTED OPERATORS 中列出的函数，禁止使用 rsi, macd, ema, sma, bbands, atr, obv, adx 等未列出的技术指标
2. 优先使用非线性变换（sign_power, tanh, sigmoid, log）捕捉市场动态
3. 组合不同类别的信号（动量+量价+波动率），而非仅调整单一信号的参数
3. 使用交互项（乘法组合）来增强因子区分度
4. 考虑条件因子（where）来捕捉不同市场状态
5. 改变时间窗口（5/10/20/40/60日）来覆盖不同周期
6. 使用衰减加权（decay_linear）来对近期数据赋予更高权重
"""

_OUTPUT_FORMAT_RULES = """
## 输出格式要求（必须严格遵守）
只返回一个因子表达式，不要任何解释、分析或推理过程。
不要使用 markdown 代码块、反引号或引号包裹。
不要以"根据分析"、"我将"、"改进的因子"等开头。
你的回复必须是恰好一行可执行的因子表达式，不要任何其他内容。

## 复杂度限制（必须遵守）
- 函数嵌套层数不能超过 5 层（例如 rank(ts_corr(close, volume, 20)) 是 2 层）
- 表达式总长度不能超过 200 个字符
- 优先使用简洁、高效的表达式，而非堆叠大量算子
"""


def _select_categories(task_id: str, iteration_index: int, n: int = 5) -> list[tuple[str, str]]:
    """Deterministically select n factor categories based on task_id + iteration_index."""
    seed_str = f"{task_id}:{iteration_index}"
    h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    indices = []
    total = len(_FACTOR_CATEGORIES)
    for i in range(total):
        indices.append((h >> (i * 3)) % 1000)
    ranked = sorted(range(total), key=lambda i: indices[i])
    return [_FACTOR_CATEGORIES[i] for i in ranked[:n]]


def build_iterate_prompt(
    expression: str,
    metrics: dict,
    score: float,
    grade: str,
    iteration_index: int,
    previous_expressions: list[str],
    task_id: str = "",
    anti_overfit: dict | None = None,
) -> tuple[str, str]:
    """Build system and user prompts for iteration LLM call.

    Uses MutationEngine for targeted diagnosis when available,
    falls back to score-based heuristics.

    Returns:
        (system_prompt, user_prompt)
    """
    from .api_server import _FACTOR_OPERATORS

    # Try mutation engine for targeted prompts
    engine = MutationEngine(
        expression=expression,
        metrics=metrics,
        score=score,
        anti_overfit=anti_overfit,
    )
    diagnosis = engine.diagnose_failure()
    system_prompt, user_prompt = engine.build_mutation_prompt(operators_doc=_FACTOR_OPERATORS)

    # Append diversity guide and anti-repeat to user prompt
    user_parts = [user_prompt]

    # Category examples (rotated)
    selected = _select_categories(task_id, iteration_index, n=5)
    user_parts.append("")
    user_parts.append("## 参考因子类别示例（可选方向）")
    for name, example in selected:
        user_parts.append(f"- {name}: {example}")

    # Anti-repeat
    if previous_expressions:
        user_parts.append("")
        user_parts.append("## 禁止重复（以下表达式已使用，不能再用或仅微调参数）")
        for expr in previous_expressions:
            user_parts.append(f"- {expr}")

    # Anti-overfit feedback
    if anti_overfit:
        user_parts.append("")
        user_parts.append(f"## 反过拟合检测结果: {anti_overfit.get('recommendation', 'N/A')} (得分: {anti_overfit.get('score', 'N/A')})")
        for test in anti_overfit.get("tests", []):
            status = "✓" if test.get("passed") else "✗"
            user_parts.append(f"  {status} {test.get('name', '')}")

    user_parts.append("")
    user_parts.append("请生成一个改进的因子表达式：")
    user_prompt = "\n".join(user_parts)

    return system_prompt, user_prompt


# ---- Duplicate detection ----

def _normalize_expression(expr: str) -> str:
    """Normalize expression for comparison: lowercase, strip spaces."""
    return re.sub(r"\s+", "", expr.lower())


def is_duplicate_expression(expr: str, existing: list[str]) -> bool:
    """Check if an expression is a duplicate of any in the existing list."""
    norm = _normalize_expression(expr)
    return any(_normalize_expression(e) == norm for e in existing)


# ---- Candidate generation ----

def _generate_single_candidate(
    parent_expression: str,
    parent_metrics: dict,
    parent_score: float,
    parent_grade: str,
    params: dict,
    market_df: pd.DataFrame,
    iteration_index: int,
    shared_expressions: list[str],
    expressions_lock: threading.Lock,
    user_id: str,
    task_id: str = "",
    max_dedup_retries: int = 4,
) -> dict:
    """Generate a single iteration candidate: LLM -> validate -> backtest -> score.

    Uses shared_expressions (protected by expressions_lock) for dedup across workers.
    Retries LLM call up to max_dedup_retries times if a duplicate is generated.
    """
    import time as _time
    from openai import OpenAI
    from .api_server import _clean_expression, _validate_parentheses

    raw_expression = "unknown"

    try:
        # Stagger concurrent calls to reduce duplicates
        _time.sleep(iteration_index * 3)

        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set")
        base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        client = OpenAI(api_key=api_key, base_url=base_url)

        # Retry loop for dedup — get a fresh snapshot each attempt
        for dedup_attempt in range(max_dedup_retries + 1):
            # 1. Build prompt with latest shared expressions
            with expressions_lock:
                previous_expressions = list(shared_expressions)

            system_prompt, user_prompt = build_iterate_prompt(
                expression=parent_expression,
                metrics=parent_metrics,
                score=parent_score,
                grade=parent_grade,
                iteration_index=iteration_index + dedup_attempt * 100,
                previous_expressions=previous_expressions,
                task_id=task_id,
            )

            # 2. Call LLM with retry
            # Increase temperature on dedup retries for more diversity
            temp = min(0.9 + dedup_attempt * 0.3, 1.8)
            last_err = None
            for attempt in range(3):
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=temp,
                        max_tokens=256,
                        timeout=60,
                    )
                    raw_expression = _clean_expression(resp.choices[0].message.content)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    logger.warning(f"LLM call attempt {attempt+1} failed: {e}")
                    _time.sleep(3 * (attempt + 1))

            if last_err:
                raise last_err

            # 3. Validate
            paren_err = _validate_parentheses(raw_expression)
            if paren_err:
                return {"expression": raw_expression, "status": "failed", "error": f"括号错误: {paren_err}"}

            try:
                dummy = pd.DataFrame({
                    "open": [1.0, 2.0, 3.0], "high": [1.1, 2.1, 3.1],
                    "low": [0.9, 1.9, 2.9], "close": [1.0, 2.0, 3.0],
                    "volume": [100, 200, 300], "amount": [100, 400, 900],
                    "pct_change": [0, 100, 50],
                })
                func = parse_expression(raw_expression)
                func(dummy)
            except Exception as e:
                return {"expression": raw_expression, "status": "failed", "error": f"表达式验证失败: {e}"}

            # 4. Atomic duplicate check-and-register
            with expressions_lock:
                if is_duplicate_expression(raw_expression, shared_expressions):
                    if dedup_attempt < max_dedup_retries:
                        logger.info(f"[{task_id}] candidate {iteration_index} duplicate on attempt {dedup_attempt}, retrying")
                        continue
                    return {"expression": raw_expression, "status": "failed", "error": "重复表达式"}
                # Claim this expression immediately so other workers see it
                shared_expressions.append(raw_expression)

            break  # got a unique, valid expression

        # 5. Run backtest
        n_groups = params.get("n_groups", 5)
        holding_period = params.get("holding_period", 5)
        result = run_factor_backtest(market_df, raw_expression, n_groups, holding_period)

        # 5a. Run anti-overfit detection (lightweight: skip placebo in iteration)
        anti_overfit_result = None
        factor_df = result.get("_factor_df")
        if factor_df is not None and len(factor_df) > 100:
            try:
                from .anti_overfit import AntiOverfitDetector
                detector = AntiOverfitDetector(factor_df, holding_period)
                # Only run fast tests (IC stability + half-life), skip expensive placebo/stress
                t1 = detector.test_ic_stability()
                t4 = detector.test_half_life()
                fast_passed = sum(1 for t in [t1, t4] if t.passed)
                fast_score = fast_passed / 2 * 100
                anti_overfit_result = {
                    "score": fast_score,
                    "recommendation": "推荐" if fast_score >= 75 else "谨慎" if fast_score >= 50 else "需改进",
                    "passed_count": fast_passed,
                    "total_count": 2,
                    "tests": [
                        {"name": t.name, "passed": t.passed, "details": t.details}
                        for t in [t1, t4]
                    ],
                    "mode": "fast",
                }
            except Exception as e:
                logger.warning(f"Anti-overfit detection failed: {e}")

        # 6. Generate report
        from .market_data import fetch_benchmark_returns
        bm_returns = None
        try:
            bm_returns = fetch_benchmark_returns(
                params.get("benchmark", "hs300"),
                params.get("start_date", "2023-01-01"),
                params.get("end_date", "2025-12-31"),
            )
        except Exception:
            pass

        user_report_dir = Path(__file__).resolve().parent.parent / "reports" / user_id
        user_report_dir.mkdir(parents=True, exist_ok=True)

        report_result = generate_report(
            result["strategy_returns"],
            benchmark_returns=bm_returns,
            title="Factor Top-Group Backtest",
            output_dir=str(user_report_dir),
        )
        report_filename = Path(report_result["report_path"]).name

        # 7. Score
        ao_score_val = anti_overfit_result.get("score") if anti_overfit_result else None
        scoring = compute_factor_score(
            backtest_summary={
                "long_short_sharpe": result["long_short_sharpe"],
                "monotonicity_score": result["monotonicity_score"],
                "spread": result["spread"],
            },
            report_metrics=report_result["metrics"],
            anti_overfit_score=ao_score_val,
        )

        return {
            "expression": raw_expression,
            "status": "success",
            "score": scoring["score"],
            "grade": scoring["grade"],
            "component_scores": scoring["component_scores"],
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
            "report_metrics": report_result["metrics"],
            "report_url": f"/api/v1/reports/{report_filename}",
            "report_filename": report_filename,
        }

    except Exception as e:
        logger.error(f"Candidate generation failed: {traceback.format_exc()}")
        return {
            "expression": raw_expression,
            "status": "failed",
            "error": str(e),
        }


def generate_iteration_candidates(
    parent_expression: str,
    parent_metrics: dict,
    parent_score: float,
    parent_grade: str,
    params: dict,
    market_df: pd.DataFrame,
    user_id: str,
    n_candidates: int = 5,
    max_concurrent: int = 3,
    on_progress: Optional[Callable[[int, dict], None]] = None,
    task_id: str = "",
) -> list[dict]:
    """Generate N candidate factor improvements in parallel.

    Args:
        parent_expression: Current factor expression.
        parent_metrics: Dict with backtest_summary and report_metrics.
        parent_score: Current factor score (0-100).
        parent_grade: Current grade (A/B/C/D).
        params: Backtest params (universe, dates, n_groups, etc.).
        market_df: Pre-loaded market data DataFrame.
        user_id: User ID for report directory.
        n_candidates: Number of candidates to generate.
        max_concurrent: Max parallel workers.
        on_progress: Callback(done_count, candidate_result) for progress updates.
        task_id: Task ID for deterministic category selection.

    Returns:
        List of candidate dicts sorted by score descending.
    """
    previous_expressions = [parent_expression]
    expressions_lock = threading.Lock()
    candidates = []
    done_count = 0

    with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        futures = {}
        for i in range(n_candidates):
            f = pool.submit(
                _generate_single_candidate,
                parent_expression=parent_expression,
                parent_metrics=parent_metrics,
                parent_score=parent_score,
                parent_grade=parent_grade,
                params=params,
                market_df=market_df,
                iteration_index=i,
                shared_expressions=previous_expressions,
                expressions_lock=expressions_lock,
                user_id=user_id,
                task_id=task_id,
            )
            futures[f] = i

        for f in as_completed(futures):
            result = f.result()
            candidates.append(result)

            done_count += 1
            if on_progress:
                on_progress(done_count, result)

    # Sort: successful first by score descending, then failed
    candidates.sort(key=lambda c: (c.get("status") == "success", c.get("score", 0)), reverse=True)
    return candidates
