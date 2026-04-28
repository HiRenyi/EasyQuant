"""Strategy code extraction and validation utilities.

Provides:
- extract_python_code(): Extract Python code from LLM markdown output
- validate_strategy_code(): AST-based validation of JoinQuant strategy code
"""

import ast
import re
from dataclasses import dataclass, field

# ---- Code Extraction ----

def extract_python_code(text: str) -> str | None:
    """Extract Python code from markdown code blocks in LLM output.

    Tries ```python blocks first, then generic ``` blocks,
    then falls back to detecting raw code without code blocks.
    """
    # Try ```python ... ``` first
    matches = re.findall(r"```python\s*\n(.*?)```", text, re.DOTALL)
    if matches:
        return _clean_strategy_code(matches[-1].strip())

    # Try generic ``` ... ```
    matches = re.findall(r"```\s*\n(.*?)```", text, re.DOTALL)
    if matches:
        for match in reversed(matches):
            if "def " in match:
                return _clean_strategy_code(match.strip())

    # Fallback: no code blocks, but text contains def initialize + def handle_data
    if "def initialize" in text and "def handle_data" in text:
        # Extract from first "def initialize" to end (or to some marker)
        idx = text.index("def initialize")
        code = text[idx:]
        # Trim trailing non-code text (e.g. explanation after code)
        # Look for a line that doesn't look like code
        lines = code.split('\n')
        code_lines = []
        for line in lines:
            # Stop at lines that look like markdown/explanation (not code)
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and not stripped.startswith('def ') \
               and not stripped.startswith('class ') and not line.startswith(' ') \
               and not line.startswith('\t') and not stripped.startswith('g.') \
               and not stripped.startswith('set_') and not stripped.startswith('order') \
               and not stripped.startswith('log.') and not stripped.startswith('if ') \
               and not stripped.startswith('elif ') and not stripped.startswith('else') \
               and not stripped.startswith('for ') and not stripped.startswith('while ') \
               and not stripped.startswith('return') and not stripped.startswith('pass') \
               and not stripped.startswith('import ') and not stripped.startswith('from ') \
               and len(code_lines) > 10:
                break
            code_lines.append(line)
        if code_lines:
            return _clean_strategy_code('\n'.join(code_lines).strip())

    return None


def _clean_strategy_code(code: str) -> str:
    """Remove problematic patterns from LLM-generated JoinQuant code.

    - Removes `from jqdata import *` (JQ auto-imports everything)
    - Removes other jqdata/jqlib imports
    - Removes leading comments/blank lines before first def
    """
    lines = code.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip jqdata/jqlib imports — JQ platform auto-imports these
        if re.match(r'^(from\s+(jqdata|jqlib|jqfactor)\s+import|import\s+(jqdata|jqlib|jqfactor))', stripped):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned)


# ---- Code Validation ----

DANGEROUS_CALLS = {
    "os.system", "os.popen", "os.exec", "os.execv", "os.execve",
    "os.remove", "os.rmdir", "os.unlink",
    "subprocess.run", "subprocess.call", "subprocess.Popen",
    "eval", "exec", "__import__", "compile",
    "open",
}

ALLOWED_IMPORTS = {
    "pandas", "numpy", "datetime", "math", "collections",
    "talib", "scipy", "statsmodels",
    "jqdata", "jqlib", "jqfactor",
}


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    has_initialize: bool = False
    has_handle_data: bool = False


def validate_strategy_code(code: str) -> ValidationResult:
    """Validate JoinQuant strategy code via AST analysis.

    Checks:
    1. Syntax correctness
    2. Required functions: initialize(context), handle_data(context, data)
    3. Dangerous function calls (os.system, subprocess, eval, exec, open, etc.)
    4. Import whitelist (pandas, numpy, jqdata, etc.)
    """
    result = ValidationResult()

    # 1. Parse AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        result.valid = False
        result.errors.append(f"语法错误: {e.msg} (第 {e.lineno} 行)")
        return result

    # 2. Check for required functions
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name == "initialize":
                result.has_initialize = True
            elif node.name == "handle_data":
                result.has_handle_data = True

    if not result.has_initialize:
        result.errors.append("缺少 initialize(context) 函数")
        result.valid = False
    if not result.has_handle_data:
        result.errors.append("缺少 handle_data(context, data) 函数")
        result.valid = False

    # 3. Check for dangerous calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_name = _get_call_name(node)
            if call_name and call_name in DANGEROUS_CALLS:
                result.errors.append(f"禁止调用: {call_name}")
                result.valid = False

    # 4. Check imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module not in ALLOWED_IMPORTS:
                    result.warnings.append(f"非常规导入: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                if module not in ALLOWED_IMPORTS:
                    result.warnings.append(f"非常规导入: from {node.module}")

    return result


def _get_call_name(node: ast.Call) -> str | None:
    """Extract function call name from AST node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            return f"{node.func.value.id}.{node.func.attr}"
    return None
