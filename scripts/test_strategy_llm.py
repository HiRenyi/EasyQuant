"""Test strategy LLM generation with different providers."""
import os, sys
from pathlib import Path

env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.is_file():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quantgpt.strategy_prompt import STRATEGY_SYSTEM_PROMPT
from quantgpt.strategy_code_utils import extract_python_code

PROMPT = "帮我写一个双均线策略，5日上穿20日买入，下穿卖出"


def test_openai(api_key, base_url, model):
    from openai import OpenAI
    print(f"Testing OpenAI: model={model}, url={base_url[:40]}")
    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": STRATEGY_SYSTEM_PROMPT},
            {"role": "user", "content": PROMPT},
        ],
        temperature=0.3,
        max_tokens=4096,
        timeout=120,
    )
    return resp.choices[0].message.content or ""


def evaluate(raw):
    print(f"  Raw length: {len(raw)}")
    print(f"  First 200: {raw[:200]}")
    code = extract_python_code(raw)
    if code:
        has_init = "def initialize" in code
        has_handle = "def handle_data" in code
        has_import = "import " in code.split("def")[0] if "def" in code else "import " in code
        print(f"  Extract: OK ({len(code)} chars)")
        print(f"  def initialize: {has_init}")
        print(f"  def handle_data: {has_handle}")
        print(f"  Has imports (BAD): {has_import}")
        if has_init and has_handle and not has_import:
            print(f"  RESULT: PASS")
        else:
            print(f"  RESULT: FAIL (format wrong)")
    else:
        print(f"  Extract: FAILED")
        print(f"  Has ```python: {'```python' in raw}")
        print(f"  Has def initialize: {'def initialize' in raw}")
        print(f"  RESULT: FAIL")
    print()
    return code


# Test configs — keys read from environment variables
configs = [
    ("OpenRouter Claude Sonnet", "openai", os.environ.get("OPENROUTER_API_KEY", ""), "https://openrouter.ai/api/v1", "anthropic/claude-sonnet-4-6"),
]

for name, provider, api_key, base_url, model in configs:
    if not api_key:
        print(f"=== {name} === SKIPPED (no API key)")
        print()
        continue
    print(f"=== {name} ===")
    try:
        raw = test_openai(api_key, base_url, model)
        evaluate(raw)
    except Exception as e:
        print(f"  ERROR: {e}")
        print()
