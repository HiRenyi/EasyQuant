"""Directed mutation engine for factor iteration.

Diagnoses failure modes from backtest metrics and selects targeted
mutation strategies to guide LLM-based factor improvement.

Enhanced with MUTATE_NONLINEAR and MUTATE_INTERACTION strategies
from XTQuant QuantaAlpha framework.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MutationStrategy(Enum):
    MUTATE_WINDOW = "mutate_window"
    MUTATE_OPERATOR = "mutate_operator"
    MUTATE_NORMALIZATION = "mutate_normalization"
    MUTATE_SIGNAL_TYPE = "mutate_signal_type"
    MUTATE_NONLINEAR = "mutate_nonlinear"
    MUTATE_INTERACTION = "mutate_interaction"
    SIMPLIFY = "simplify"
    REGENERATE_FULL = "regenerate_full"


@dataclass
class Diagnosis:
    strategy: MutationStrategy
    reason: str
    details: dict


_OPERATOR_REPLACEMENTS = {
    "ts_mean": ["decay_linear", "ts_sum", "ts_median"],
    "ts_std": ["ts_mean", "ts_rank", "ts_mad"],
    "ts_delta": ["ts_shift", "ts_rank"],
    "ts_corr": ["ts_cov", "ts_rank"],
    "ts_rank": ["rank", "zscore"],
    "rank": ["zscore", "scale", "tanh"],
    "decay_linear": ["ts_mean", "ts_sum"],
    "ts_max": ["ts_min", "ts_argmax"],
    "ts_min": ["ts_max", "ts_argmin"],
}

_NORMALIZATION_OPS = {"rank", "zscore", "scale", "tanh", "sigmoid"}
_NONLINEAR_OPS = {"tanh", "sigmoid", "power", "sign_power", "log", "sqrt", "exp"}


class MutationEngine:
    """Diagnose factor failure modes and build targeted mutation prompts."""

    def __init__(self, expression: str, metrics: dict, score: float,
                 anti_overfit: dict | None = None):
        self.expression = expression
        self.metrics = metrics
        self.score = score
        self.anti_overfit = anti_overfit
        self.backtest = metrics.get("backtest_summary", {})
        self.report = metrics.get("report_metrics", {})

    def diagnose_failure(self) -> Diagnosis:
        """Analyze metrics and select the best mutation strategy."""
        ic_mean = self.backtest.get("ic_mean", 0)
        ic_ir = self.backtest.get("ic_ir", 0)
        nesting = self._count_nesting(self.expression)
        has_norm = self._has_normalization(self.expression)
        has_nonlinear = self._has_nonlinear(self.expression)

        # 1. Score < 20: completely regenerate
        if self.score < 20:
            return Diagnosis(MutationStrategy.REGENERATE_FULL,
                f"极低评分({self.score}), 需要完全重写", {"score": self.score})

        # 2. IC near zero: operator issue
        if abs(ic_mean) < 0.005:
            return Diagnosis(MutationStrategy.MUTATE_OPERATOR,
                f"IC接近零({ic_mean:.4f}), 当前算子无预测能力",
                {"ic_mean": ic_mean, "suggested_replacements": self._suggest_replacements()})

        # 3. Negative IC: signal direction wrong
        if ic_mean < -0.01:
            return Diagnosis(MutationStrategy.MUTATE_SIGNAL_TYPE,
                f"IC为负({ic_mean:.4f}), 因子方向反转", {"ic_mean": ic_mean})

        # 4. Deep nesting: simplify
        if nesting > 8:
            return Diagnosis(MutationStrategy.SIMPLIFY,
                f"嵌套层数过深({nesting}层), 需适当简化", {"nesting_depth": nesting})

        # 5. Medium score + no nonlinear: add nonlinear transforms
        if 20 <= self.score < 50 and not has_nonlinear:
            return Diagnosis(MutationStrategy.MUTATE_NONLINEAR,
                f"评分中等({self.score})且无非线性变换, 建议引入tanh/power等",
                {"score": self.score, "has_nonlinear": False})

        # 6. Low IR + no normalization: add normalization
        if ic_ir < 0.5 and not has_norm:
            return Diagnosis(MutationStrategy.MUTATE_NORMALIZATION,
                f"IR较低({ic_ir:.2f})且无标准化, 建议添加rank/zscore",
                {"ic_ir": ic_ir, "has_normalization": has_norm})

        # 7. Single-signal factor: add interaction
        if self._is_single_signal():
            return Diagnosis(MutationStrategy.MUTATE_INTERACTION,
                "单信号因子, 建议组合多个信号源增强预测能力",
                {"signal_count": 1})

        # 8. Default: adjust window parameters
        return Diagnosis(MutationStrategy.MUTATE_WINDOW,
            "默认策略: 调整时序窗口参数以优化IC/IR",
            {"ic_mean": ic_mean, "ic_ir": ic_ir, "current_windows": self._extract_windows()})

    def build_mutation_prompt(self, operators_doc: str = "") -> tuple[str, str]:
        """Build (system_prompt, user_prompt) based on diagnosis."""
        diagnosis = self.diagnose_failure()
        strategy = diagnosis.strategy

        sys_parts = [
            "你是一个量化因子表达式优化专家。基于诊断结果，使用定向突变策略改进因子。",
            "",
        ]
        if operators_doc:
            sys_parts.append(operators_doc)
            sys_parts.append("")
        sys_parts.extend([
            "## 输出格式要求（必须严格遵守）",
            "只返回一个因子表达式，不要任何解释、分析或推理过程。",
            "不要使用 markdown 代码块、反引号或引号包裹。",
            "你的回复必须是恰好一行可执行的因子表达式。",
            "",
            "## 复杂度限制",
            "- 函数嵌套层数不能超过 10 层",
            "- 表达式总长度不能超过 500 个字符",
            "",
            "## 多样性要求",
            "- 新表达式必须与当前表达式结构不同",
            "- 禁止仅修改常数或窗口参数的微小变化",
            "- 鼓励使用非线性变换（tanh, sigmoid, power）",
            "- 鼓励组合多个信号源（量价交互、动量+波动等）",
        ])
        system_prompt = "\n".join(sys_parts)

        user_parts = [
            f"当前因子: {self.expression}",
            f"评分: {self.score}/100",
            f"IC均值: {self.backtest.get('ic_mean', 'N/A')}",
            f"IC_IR: {self.backtest.get('ic_ir', 'N/A')}",
            f"单调性: {self.backtest.get('monotonicity_score', 'N/A')}",
            f"换手率: {self.backtest.get('turnover', 'N/A')}",
            "",
            "## 诊断结果",
            f"策略: {strategy.value}",
            f"原因: {diagnosis.reason}",
            "",
        ]

        if strategy == MutationStrategy.MUTATE_WINDOW:
            windows = self._extract_windows()
            user_parts.append("## 突变指令: 调整时序窗口")
            user_parts.append(f"当前窗口参数: {windows}")
            user_parts.append("请尝试不同的窗口长度（5/10/20/40/60），保留核心算子结构。")

        elif strategy == MutationStrategy.MUTATE_OPERATOR:
            replacements = self._suggest_replacements()
            user_parts.append("## 突变指令: 替换核心算子")
            user_parts.append(f"建议替换方案: {replacements}")
            user_parts.append("当前算子无预测能力，请替换为其他类型的时序/截面算子。")

        elif strategy == MutationStrategy.MUTATE_NORMALIZATION:
            user_parts.append("## 突变指令: 添加标准化")
            user_parts.append("请在最外层添加 rank() 或 zscore()，或在关键子表达式上添加 scale() / tanh()。")

        elif strategy == MutationStrategy.MUTATE_SIGNAL_TYPE:
            user_parts.append("## 突变指令: 翻转因子方向")
            user_parts.append("因子IC为负，请在表达式前添加 -1 * 或调整信号逻辑。")

        elif strategy == MutationStrategy.MUTATE_NONLINEAR:
            user_parts.append("## 突变指令: 引入非线性变换")
            user_parts.append("当前因子仅使用线性运算。请引入非线性变换增强表达能力：")
            user_parts.append("- tanh(x): 压缩极端值，增强鲁棒性")
            user_parts.append("- power(x, 0.5) 或 sign_power(x, 0.5): 弱化极端值影响")
            user_parts.append("- sigmoid(x): S型映射，适合二值化信号")
            user_parts.append("- 组合示例: rank(tanh(ts_delta(close, 20) / ts_std(close, 20)))")

        elif strategy == MutationStrategy.MUTATE_INTERACTION:
            user_parts.append("## 突变指令: 组合多信号源")
            user_parts.append("当前因子仅使用单一信号。请组合多个信号源：")
            user_parts.append("- 量价交互: rank(volume_signal) * rank(price_signal)")
            user_parts.append("- 动量+波动: rank(momentum) * rank(-volatility)")
            user_parts.append("- 条件组合: where(vol_condition, signal_a, signal_b)")
            user_parts.append("- 加权组合: 0.6*rank(signal_a) + 0.4*rank(signal_b)")

        elif strategy == MutationStrategy.SIMPLIFY:
            user_parts.append("## 突变指令: 适当简化表达式")
            user_parts.append(f"当前嵌套深度: {self._count_nesting(self.expression)} 层")
            user_parts.append("请减少嵌套到6-8层以内，移除冗余变换，保留核心预测信号。")

        elif strategy == MutationStrategy.REGENERATE_FULL:
            user_parts.append("## 突变指令: 完全重写")
            user_parts.append("当前因子完全无效，请从零开始设计一个新的因子表达式。")
            user_parts.append("建议尝试: 动量、反转、量价相关、波动率等经典因子类别。")

        user_parts.append("")
        user_parts.append("请生成改进后的因子表达式：")
        user_prompt = "\n".join(user_parts)

        return system_prompt, user_prompt

    def _count_nesting(self, expr: str) -> int:
        max_depth = depth = 0
        for ch in expr:
            if ch == '(':
                depth += 1
                max_depth = max(max_depth, depth)
            elif ch == ')':
                depth -= 1
        return max_depth

    def _has_normalization(self, expr: str) -> bool:
        expr_lower = expr.lower()
        return any(op + "(" in expr_lower for op in _NORMALIZATION_OPS)

    def _has_nonlinear(self, expr: str) -> bool:
        expr_lower = expr.lower()
        return any(op + "(" in expr_lower for op in _NONLINEAR_OPS)

    def _is_single_signal(self) -> bool:
        """Check if expression uses only one base variable (close, volume, etc.)."""
        base_vars = {"open", "high", "low", "close", "volume", "amount", "vwap"}
        expr_lower = self.expression.lower()
        used = [v for v in base_vars if v in expr_lower]
        return len(used) <= 1

    def _extract_windows(self) -> list[int]:
        pattern = r'ts_\w+\([^,]+,\s*(\d+)\)'
        matches = re.findall(pattern, self.expression)
        return sorted(set(int(m) for m in matches))

    def _suggest_replacements(self) -> dict[str, list[str]]:
        suggestions = {}
        expr_lower = self.expression.lower()
        for op, replacements in _OPERATOR_REPLACEMENTS.items():
            if op + "(" in expr_lower:
                suggestions[op] = replacements
        return suggestions
