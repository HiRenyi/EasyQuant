"""Crossover engine — recombine successful segments from iteration history.

Ported from XTQuant QuantaAlpha: orchestration/src/ai_runtime/agent/crossover_engine.py
"""

import logging

logger = logging.getLogger(__name__)


def extract_top_segments(iterations: list[dict], min_score_ratio: float = 0.5) -> list[dict]:
    """Extract high-scoring expressions from iteration history.

    Args:
        iterations: List of {expression, score, ...} dicts.
        min_score_ratio: Minimum score as ratio of best score to include.

    Returns:
        Top 3-5 segments sorted by score descending.
    """
    if not iterations:
        return []

    best_score = max(it.get("score", 0) or 0 for it in iterations)
    threshold = best_score * min_score_ratio

    qualified = [
        it for it in iterations
        if (it.get("score", 0) or 0) >= threshold and it.get("expression")
    ]
    qualified.sort(key=lambda x: x.get("score", 0), reverse=True)
    return qualified[:5]


def build_crossover_prompt(
    segments: list[dict],
    current_expression: str,
    current_score: float,
    operators_doc: str = "",
) -> tuple[str, str]:
    """Build LLM prompt for crossover recombination.

    Returns:
        (system_prompt, user_prompt) tuple.
    """
    sys_parts = [
        "你是一个量化因子表达式优化专家。你的任务是分析多个历史高分因子表达式，",
        "提取各自的成功要素（算子选择、时间窗口、信号类型、标准化方式），",
        "然后创造性地重组为一个全新的、更优的因子表达式。",
        "",
    ]
    if operators_doc:
        sys_parts.append(operators_doc)
        sys_parts.append("")
    sys_parts.extend([
        "## 重组策略",
        "- 分析每个高分片段的核心逻辑（为什么它有效）",
        "- 提取成功要素：时间窗口、算子类型、信号方向、标准化方式",
        "- 创造性组合：A的时间窗口 + B的算子 + C的标准化",
        "- 或：加权组合多个信号源",
        "- 引入非线性变换（tanh, sigmoid, power）增强表达能力",
        "",
        "## 输出格式",
        "只返回一个因子表达式，不要任何解释。",
        "不要使用 markdown 代码块。",
        "表达式必须是一行可执行的因子公式。",
    ])
    system_prompt = "\n".join(sys_parts)

    user_parts = [
        f"当前因子: {current_expression}",
        f"当前评分: {current_score}/100",
        "",
        "## 历史高分片段（按评分排序）",
    ]
    for i, seg in enumerate(segments, 1):
        expr = seg.get("expression", "")
        score = seg.get("score", 0)
        user_parts.append(f"  {i}. [{score}分] {expr}")

    user_parts.extend([
        "",
        "## 任务",
        "分析以上高分因子的成功要素，创造性地重组为一个全新的因子表达式。",
        "新表达式必须与以上所有表达式结构不同，但融合它们的优势。",
        "",
        "请生成重组后的因子表达式：",
    ])
    user_prompt = "\n".join(user_parts)

    return system_prompt, user_prompt
