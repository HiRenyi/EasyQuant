"""
Factor Expression Parser

Parses simple factor expressions and returns callables
that operate on DataFrames.

Supported operations:
- rank(col)           : cross-sectional rank
- zscore(col)         : cross-sectional z-score standardization
- sign(col)           : sign function
- log(col)            : natural log
- abs(col)            : absolute value
- scale(col)          : standardize to [0, 1] range
- tanh(col)           : hyperbolic tangent
- sigmoid(col)        : logistic sigmoid (1/(1+exp(-x)))
- exp(col)            : exponential (capped to avoid overflow)
- sqrt(col)           : square root (negative values clipped to 0)
- ts_mean(col, N)     : rolling mean over N periods
- ts_std(col, N)      : rolling std over N periods
- ts_max(col, N)      : rolling max over N periods
- ts_min(col, N)      : rolling min over N periods
- ts_sum(col, N)      : rolling sum over N periods
- ts_shift(col, N)    : shift values by N periods (positive=lag, negative=lead)
- ts_delta(col, N)    : N-period change
- ts_rank(col, N)     : rolling percentile rank (returns 0~1, e.g. 0.8 means top 80%)
- ts_argmax(col, N)   : position of max in rolling window
- ts_argmin(col, N)   : position of min in rolling window
- ts_corr(col1, col2, N) : rolling correlation
- ts_cov(col1, col2, N)  : rolling covariance
- decay_linear(col, N) : linear decay weights over N periods
- product(col, N)     : rolling product over N periods
- power(base, exp)    : power operation (base ** exp)
- sign_power(base, exp) : sign(base) * (abs(base) ** exp)
- max(a, b)           : element-wise maximum
- min(a, b)           : element-wise minimum
- clip(expr, lo, hi)  : clip values to [lo, hi] range
- where(cond, t, f)   : conditional selection (t if cond else f)
- indneutralize(col, industry) : industry neutralization (placeholder)
- Arithmetic: +, -, *, /, ^
- Comparison: >, <, >=, <=, ==, !=
- Logical: and, or, &, |

Special variables:
- vwap                : volume-weighted average price
- adv{N}              : N-day average daily volume (e.g., adv20)
- returns             : daily returns
- cap                 : market capitalization
- day                 : day of month (1-31)
- weekday             : day of week (0=Monday, 4=Friday)
- month               : month (1-12)

Fundamental data variables (quarterly financials, aligned to daily via pubDate):
  Profitability:
  - roe              : 平均净资产收益率
  - np_margin        : 净利润率
  - gp_margin        : 毛利率
  - net_profit       : 净利润(元)
  - eps_ttm          : 每股收益(TTM)
  - revenue          : 营业收入(元)
  - total_share      : 总股本
  - float_share      : 流通股本
  Growth:
  - yoy_ni           : 净利润同比增长率
  - yoy_equity       : 净资产同比增长率
  - yoy_asset        : 总资产同比增长率
  - yoy_pni          : 归母净利润同比增长率
  Balance sheet:
  - current_ratio    : 流动比率
  - debt_ratio       : 资产负债率
  - equity_multiplier: 权益乘数
  Operations:
  - asset_turnover   : 总资产周转率
  - inv_turnover     : 存货周转率
  - dupont_roe       : 杜邦分析ROE
  - dupont_asset_turn: 杜邦资产周转率
  Cash flow:
  - cfo_to_np        : 经营现金流/净利润
  Valuation (derived from close + fundamental):
  - pe               : 市盈率 (close * total_share / net_profit)
  - pb               : 市净率
  - ps               : 市销率 (close * total_share / revenue)

Operator aliases (for Alpha101 compatibility):
- delta(col, N)       : alias for ts_delta
- delay(col, N)       : alias for ts_shift
- covariance(col1, col2, N) : alias for ts_cov
- correlation(col1, col2, N) : alias for ts_corr
- IndNeutralize(col, industry) : alias for indneutralize

Syntax extensions:
- Ternary operator: (condition ? true_value : false_value)
- Power operator: base ^ exponent (equivalent to power(base, exponent))
"""

import re
import numpy as np
import pandas as pd
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)


class ExpressionParser:
    """Parse factor expressions into callable functions."""

    MAX_WINDOW = 500
    MAX_DEPTH = 40
    MAX_EXPRESSION_LENGTH = 1000

    # Pattern: func_name(args)
    _FUNC_PATTERN = re.compile(
        r'^(\w+)\((.+)\)$'
    )

    # Operator aliases for compatibility with Alpha101 and other factor libraries
    _OPERATOR_ALIASES = {
        'delta': 'ts_delta',
        'delay': 'ts_shift',
        'covariance': 'ts_cov',
        'correlation': 'ts_corr',
        'IndNeutralize': 'indneutralize',  # Alpha101 uses capital I
    }

    # Special variable mappings (computed from DataFrame columns)
    _SPECIAL_VARS = {
        'vwap': lambda df: (df['close'] * df['volume']).rolling(1).sum() / df['volume'].rolling(1).sum(),
        'returns': lambda df: df['close'].pct_change(),
        'cap': lambda df: df.get('market_cap', df['close'] * df.get('shares', 1)),  # fallback if no market_cap
        'day': lambda df: pd.Series(df['trade_date'].dt.day, index=df.index, dtype=float),
        'weekday': lambda df: pd.Series(df['trade_date'].dt.weekday, index=df.index, dtype=float),  # 0=Mon, 4=Fri
        'month': lambda df: pd.Series(df['trade_date'].dt.month, index=df.index, dtype=float),
    }

    # Supported unary functions (column -> Series)
    _UNARY_OPS = {
        'rank': lambda s: s.rank(pct=True),
        'log': lambda s: np.log(s.clip(lower=1e-10)),
        'abs': lambda s: s.abs(),
        'sign': lambda s: np.sign(s),
        'zscore': lambda s: (s - s.mean()) / (s.std() + 1e-10),
        'scale': lambda s: (s - s.min()) / (s.max() - s.min() + 1e-10),  # normalize to [0, 1]
        'tanh': lambda s: np.tanh(s),
        'sigmoid': lambda s: 1.0 / (1.0 + np.exp(-s.clip(-500, 500))),
        'exp': lambda s: np.exp(s.clip(upper=500)),  # clip to avoid overflow
        'sqrt': lambda s: np.sqrt(s.clip(lower=0)),
    }

    # Supported time-series functions (column, window -> Series)
    _TS_OPS = {
        'ts_mean': lambda s, w: s.rolling(w, min_periods=1).mean(),
        'ts_std': lambda s, w: s.rolling(w, min_periods=1).std(),
        'ts_max': lambda s, w: s.rolling(w, min_periods=1).max(),
        'ts_min': lambda s, w: s.rolling(w, min_periods=1).min(),
        'ts_sum': lambda s, w: s.rolling(w, min_periods=1).sum(),
        'ts_shift': lambda s, w: s.shift(w),
        'ts_delta': lambda s, w: s - s.shift(w),
        'ts_rank': lambda s, w: s.rolling(w, min_periods=1).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False),
        'ts_argmax': lambda s, w: s.rolling(w, min_periods=1).apply(lambda x: x.argmax(), raw=True),
        'ts_argmin': lambda s, w: s.rolling(w, min_periods=1).apply(lambda x: x.argmin(), raw=True),
        'decay_linear': lambda s, w: s.rolling(w, min_periods=1).apply(
            lambda x: np.dot(x, np.arange(1, len(x) + 1)) / np.sum(np.arange(1, len(x) + 1)) if len(x) > 0 else np.nan,
            raw=True
        ),
        'product': lambda s, w: s.rolling(w, min_periods=1).apply(lambda x: np.prod(x), raw=True),
    }

    # Supported dual-column time-series functions (col1, col2, window -> Series)
    _TS_DUAL_OPS = {
        'ts_corr': lambda s1, s2, w: s1.rolling(w, min_periods=1).corr(s2),
        'ts_cov': lambda s1, s2, w: s1.rolling(w, min_periods=1).cov(s2),
    }

    # Supported binary operations (base, exponent -> Series)
    _BINARY_OPS = {
        'power': lambda s, exp: s ** exp,
        'pow': lambda s, exp: s ** exp,  # alias
        'sign_power': lambda s, exp: np.sign(s) * (np.abs(s) ** exp),
        'max': lambda a, b: np.maximum(a, b),
        'min': lambda a, b: np.minimum(a, b),
    }

    # Industry neutralization (placeholder - requires industry data)
    _NEUTRALIZE_OPS = {
        'indneutralize': lambda s, industry: s - s.groupby(industry).transform('mean'),  # simple demeaning
    }

    def parse(self, expression: str, _depth: int = 0) -> Callable[[pd.DataFrame], pd.Series]:
        """Parse an expression string and return a callable.

        Args:
            expression: Factor expression, e.g. "rank(close/open)",
                        "ts_mean(volume, 20)"

        Returns:
            A callable that takes a DataFrame and returns a Series.
        """
        if _depth > self.MAX_DEPTH:
            raise ValueError(f"Expression nesting too deep (max {self.MAX_DEPTH})")

        expression = expression.strip()

        if len(expression) > self.MAX_EXPRESSION_LENGTH:
            raise ValueError(f"Expression too long (max {self.MAX_EXPRESSION_LENGTH} chars)")

        # Store depth for sub-calls
        self._depth = _depth

        # Preprocess: convert C-style ternary operators to Python style
        if _depth == 0:
            expression = self._convert_ternary_operators(expression)

        logger.info(f"Parsing expression: {expression}")

        # Try to match a function call at the outermost level.
        func_match = self._match_function_call(expression)
        if func_match is not None:
            func_name, args_str, remainder = func_match
            if not remainder:
                return self._build_function(func_name, args_str)

        # Otherwise treat as arithmetic column expression
        return self._build_arithmetic(expression)

    @staticmethod
    def _match_function_call(expression: str) -> Optional[tuple]:
        """Match a function call at the start of expression.

        Returns (func_name, args_str, remainder) or None.
        remainder is the part after the closing paren (stripped).
        """
        m = re.match(r'^(\w+)\(', expression)
        if not m:
            return None

        func_name = m.group(1).lower()
        start = m.end() - 1  # index of '('
        depth = 0
        for i in range(start, len(expression)):
            if expression[i] == '(':
                depth += 1
            elif expression[i] == ')':
                depth -= 1
                if depth == 0:
                    args_str = expression[start + 1:i]
                    remainder = expression[i + 1:].strip()
                    return (func_name, args_str, remainder)
        return None

    def _sub_parse(self, expr: str) -> Callable[[pd.DataFrame], pd.Series]:
        """Parse a sub-expression, incrementing depth."""
        return self.parse(expr, self._depth + 1)

    def _validate_window(self, window: int, func_name: str) -> int:
        """Validate rolling window size."""
        if window < 1:
            raise ValueError(f"{func_name}: window must be >= 1, got {window}")
        if window > self.MAX_WINDOW:
            raise ValueError(f"{func_name}: window too large (max {self.MAX_WINDOW}), got {window}")
        return window

    def _build_function(
        self, func_name: str, args_str: str
    ) -> Callable[[pd.DataFrame], pd.Series]:
        """Build a callable for a named function."""

        # Apply operator aliases (e.g., delta -> ts_delta, delay -> ts_shift)
        func_name = self._OPERATOR_ALIASES.get(func_name, func_name)

        if func_name in self._UNARY_OPS:
            inner = self._sub_parse(args_str)
            op = self._UNARY_OPS[func_name]
            return lambda df, _op=op, _inner=inner: _op(_inner(df))

        if func_name in self._TS_OPS:
            parts = self._split_top_level(args_str)
            if len(parts) != 2:
                raise ValueError(
                    f"{func_name} requires exactly 2 arguments: (column, window)"
                )
            inner = self._sub_parse(parts[0].strip())
            window = self._validate_window(int(parts[1].strip()), func_name)
            op = self._TS_OPS[func_name]
            return lambda df, _op=op, _inner=inner, _w=window: _op(_inner(df), _w)

        if func_name in self._TS_DUAL_OPS:
            parts = self._split_top_level(args_str)
            if len(parts) != 3:
                raise ValueError(
                    f"{func_name} requires exactly 3 arguments: (column1, column2, window)"
                )
            inner1 = self._sub_parse(parts[0].strip())
            inner2 = self._sub_parse(parts[1].strip())
            window = self._validate_window(int(parts[2].strip()), func_name)
            op = self._TS_DUAL_OPS[func_name]
            return lambda df, _op=op, _i1=inner1, _i2=inner2, _w=window: _op(_i1(df), _i2(df), _w)

        if func_name in self._BINARY_OPS:
            parts = self._split_top_level(args_str)
            if len(parts) != 2:
                raise ValueError(
                    f"{func_name} requires exactly 2 arguments"
                )
            base_fn = self._sub_parse(parts[0].strip())
            exp_fn = self._sub_parse(parts[1].strip())
            op = self._BINARY_OPS[func_name]
            return lambda df, _op=op, _base=base_fn, _exp=exp_fn: _op(_base(df), _exp(df))

        if func_name in self._NEUTRALIZE_OPS:
            raise ValueError("indneutralize is not supported (requires industry classification data)")

        if func_name == 'clip':
            parts = self._split_top_level(args_str)
            if len(parts) != 3:
                raise ValueError("clip requires exactly 3 arguments: (expr, lower, upper)")
            inner = self._sub_parse(parts[0].strip())
            lower_fn = self._sub_parse(parts[1].strip())
            upper_fn = self._sub_parse(parts[2].strip())
            return lambda df, _inner=inner, _lo=lower_fn, _hi=upper_fn: _inner(df).clip(lower=_lo(df), upper=_hi(df))

        if func_name == 'where':
            parts = self._split_top_level(args_str)
            if len(parts) != 3:
                raise ValueError("where requires exactly 3 arguments: (condition, true_value, false_value)")
            cond_fn = self._sub_parse(parts[0].strip())
            true_fn = self._sub_parse(parts[1].strip())
            false_fn = self._sub_parse(parts[2].strip())
            return lambda df, _c=cond_fn, _t=true_fn, _f=false_fn: _t(df).where(_c(df).astype(bool), _f(df))

        raise ValueError(f"Unknown function: {func_name}")

    def _build_arithmetic(
        self, expression: str
    ) -> Callable[[pd.DataFrame], pd.Series]:
        """Build a callable for simple arithmetic on columns.

        Supports: col, col/col, col*col, col+col, col-col, col^col, and numeric literals.
        Also supports special variables: vwap, adv{N}, returns, cap.
        Also supports Python ternary operator: value_if_true if condition else value_if_false
        Also supports comparison operators: >, <, >=, <=, ==, !=
        """
        expression = expression.strip()

        # Check for Python ternary operator (if...else)
        # Pattern: value_if_true if condition else value_if_false
        if ' if ' in expression and ' else ' in expression:
            # Find the positions of 'if' and 'else' at the top level
            if_pos = self._find_keyword(expression, ' if ')
            else_pos = self._find_keyword(expression, ' else ')

            if if_pos is not None and else_pos is not None and if_pos < else_pos:
                true_val_expr = expression[:if_pos].strip()
                condition_expr = expression[if_pos + 4:else_pos].strip()
                false_val_expr = expression[else_pos + 6:].strip()

                true_val_fn = self._sub_parse(true_val_expr)
                condition_fn = self._sub_parse(condition_expr)
                false_val_fn = self._sub_parse(false_val_expr)

                return lambda df, _t=true_val_fn, _c=condition_fn, _f=false_val_fn: (
                    _t(df).where(_c(df) > 0, _f(df))
                )

        # Try logical operators (lowest precedence, evaluated first during parsing)
        for op_str, op_fn in [
            (' or ', lambda a, b: ((a.astype(bool)) | (b.astype(bool))).astype(float)),
            (' and ', lambda a, b: ((a.astype(bool)) & (b.astype(bool))).astype(float)),
        ]:
            idx = self._find_keyword(expression, op_str)
            if idx is not None:
                left = self._sub_parse(expression[:idx])
                right = self._sub_parse(expression[idx + len(op_str):])
                return lambda df, _l=left, _r=right, _op=op_fn: _op(_l(df), _r(df))

        # Try bitwise logical operators (& and |, same semantics as and/or for conditions)
        for op_str, op_fn in [
            ('|', lambda a, b: ((a.astype(bool)) | (b.astype(bool))).astype(float)),
            ('&', lambda a, b: ((a.astype(bool)) & (b.astype(bool))).astype(float)),
        ]:
            idx = self._find_operator(expression, op_str)
            if idx is not None:
                left = self._sub_parse(expression[:idx])
                right = self._sub_parse(expression[idx + len(op_str):])
                return lambda df, _l=left, _r=right, _op=op_fn: _op(_l(df), _r(df))

        # Try comparison operators
        for op_str, op_fn in [
            ('>=', lambda a, b: (a >= b).astype(float)),
            ('<=', lambda a, b: (a <= b).astype(float)),
            ('==', lambda a, b: (a == b).astype(float)),
            ('!=', lambda a, b: (a != b).astype(float)),
            ('>', lambda a, b: (a > b).astype(float)),
            ('<', lambda a, b: (a < b).astype(float)),
        ]:
            idx = self._find_operator(expression, op_str)
            if idx is not None:
                left = self._sub_parse(expression[:idx])
                right = self._sub_parse(expression[idx + len(op_str):])
                return lambda df, _l=left, _r=right, _op=op_fn: _op(_l(df), _r(df))

        # Try binary operators in order of precedence (lowest first)
        for op_char, op_fn in [
            ('+', lambda a, b: a + b),
            ('-', lambda a, b: a - b),
            ('*', lambda a, b: a * b),
            ('/', lambda a, b: a / b.replace(0, np.nan)),
            ('^', lambda a, b: a ** b),
        ]:
            idx = self._find_operator(expression, op_char)
            if idx is not None:
                left = self._sub_parse(expression[:idx])
                right = self._sub_parse(expression[idx + 1:])
                return lambda df, _l=left, _r=right, _op=op_fn: _op(_l(df), _r(df))

        # Unary negation: -expr  (treat as 0 - expr)
        if expression.startswith('-'):
            inner = self._sub_parse(expression[1:])
            return lambda df, _inner=inner: -_inner(df)

        # Strip outer parentheses
        if expression.startswith('(') and expression.endswith(')'):
            return self._sub_parse(expression[1:-1])

        # Numeric literal
        try:
            val = float(expression)
            return lambda df, _v=val: pd.Series(_v, index=df.index)
        except ValueError:
            pass

        # Special variables (vwap, returns, cap) — case-insensitive
        expr_lower = expression.lower()
        if expr_lower in self._SPECIAL_VARS:
            var_fn = self._SPECIAL_VARS[expr_lower]
            return lambda df, _fn=var_fn: _fn(df)

        # Average daily volume: adv{N} (e.g., adv20, adv60) — case-insensitive
        if expr_lower.startswith('adv') and expr_lower[3:].isdigit():
            window = self._validate_window(int(expr_lower[3:]), 'adv')
            return lambda df, _w=window: df['volume'].rolling(_w, min_periods=1).mean()

        # Column reference — only allow known columns (case-insensitive)
        col_name = expr_lower.strip()
        from .fundamental_data import ALL_FUNDAMENTAL_NAMES
        _ALLOWED_COLUMNS = {'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_change', 'market_cap', 'shares'} | ALL_FUNDAMENTAL_NAMES
        # Common LLM alias mapping — redirect invalid names to valid ones
        _ALIAS_MAP = {
            'pe_ratio': 'pe', 'pe_ttm': 'pe', 'pb_ratio': 'pb', 'ps_ratio': 'ps',
            'eps': 'eps_ttm', 'roe_avg': 'roe', 'roa': 'roe',
        }
        # Unsupported variables — give clear error with suggestion
        _UNSUPPORTED = {
            'dividend_yield': '系统不支持股息率(dividend_yield)，可用 eps_ttm(每股收益) 或 cfo_to_np(现金流/净利润) 替代',
            'div_yield': '系统不支持股息率(div_yield)，可用 eps_ttm(每股收益) 或 cfo_to_np(现金流/净利润) 替代',
            'bps': '系统不支持每股净资产(bps)，可用 pb(市净率) 替代',
            'nav': '系统不支持净资产(nav)，可用 pb(市净率) 替代',
        }
        if col_name in _UNSUPPORTED:
            raise ValueError(_UNSUPPORTED[col_name])
        col_name = _ALIAS_MAP.get(col_name, col_name)
        if col_name not in _ALLOWED_COLUMNS:
            raise ValueError(f"Unknown column or variable: {col_name!r}")
        return lambda df, _c=col_name: df[_c]

    @staticmethod
    def _find_keyword(expr: str, keyword: str) -> Optional[int]:
        """Find the rightmost top-level occurrence of a keyword (e.g., ' if ', ' else ')."""
        depth = 0
        result = None
        keyword_len = len(keyword)

        for i in range(len(expr) - keyword_len + 1):
            ch = expr[i]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif depth == 0 and expr[i:i+keyword_len] == keyword:
                result = i

        return result

    @staticmethod
    def _find_operator(expr: str, op: str) -> Optional[int]:
        """Find the rightmost top-level occurrence of an operator."""
        depth = 0
        result = None
        op_len = len(op)
        i = 0
        while i < len(expr):
            ch = expr[i]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif depth == 0 and i > 0 and expr[i:i + op_len] == op:
                if op_len == 1 and ch in '<>=!':
                    # Single-char op: skip if it's part of a two-char operator
                    next_ch = expr[i + 1] if i + 1 < len(expr) else ''
                    prev_ch = expr[i - 1] if i > 0 else ''
                    if next_ch == '=' or (ch == '=' and prev_ch in '<>!='):
                        i += 1
                        continue
                result = i
            i += 1
        return result

    @staticmethod
    def _split_top_level(s: str) -> list:
        """Split a string by commas at the top level (outside parentheses)."""
        parts = []
        depth = 0
        current = []
        for ch in s:
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth -= 1
                current.append(ch)
            elif ch == ',' and depth == 0:
                parts.append(''.join(current))
                current = []
            else:
                current.append(ch)
        if current:
            parts.append(''.join(current))
        return parts

    @staticmethod
    def _convert_ternary_operators(expression: str) -> str:
        """Convert C-style ternary operators to Python style.

        Converts: (condition) ? true_value : false_value
        To:       (true_value if condition else false_value)

        Args:
            expression: Expression that may contain C-style ternary operators

        Returns:
            Expression with Python-style ternary operators

        Examples:
            >>> ExpressionParser._convert_ternary_operators("((x > 0) ? a : b)")
            '((a if x > 0 else b))'
            >>> ExpressionParser._convert_ternary_operators("rank(ts_argmax(sign_power(((returns < 0) ? ts_std(returns, 20) : close), 2), 5))")
            'rank(ts_argmax(sign_power(((ts_std(returns, 20) if returns < 0 else close)), 2), 5))'
        """
        max_iterations = 20
        iteration = 0

        # Pattern: (condition) ? true_value : false_value
        # Use non-greedy matching to avoid crossing multiple ternary expressions
        pattern = r'\(([^()]+)\)\s*\?\s*([^:]+?)\s*:\s*([^)]+?)(?=\))'

        while '?' in expression and iteration < max_iterations:
            iteration += 1
            old_expression = expression

            def replace_ternary(match):
                condition = match.group(1).strip()
                true_val = match.group(2).strip()
                false_val = match.group(3).strip()
                return f"({true_val} if {condition} else {false_val})"

            # Replace one ternary operator at a time (from innermost)
            expression = re.sub(pattern, replace_ternary, expression, count=1)

            # If no change, stop iteration
            if expression == old_expression:
                break

        return expression


def parse_expression(expression: str) -> Callable[[pd.DataFrame], pd.Series]:
    """Convenience function to parse a factor expression.

    Args:
        expression: e.g. "rank(close/open)", "ts_mean(volume, 20)"

    Returns:
        Callable that takes a DataFrame and returns factor values as a Series.
    """
    return ExpressionParser().parse(expression)
