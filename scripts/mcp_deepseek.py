"""MCP server that exposes DeepSeek API as a tool for Claude Code.

Usage:
    DEEPSEEK_API_KEY=sk-xxx python scripts/mcp_deepseek.py

Reads DEEPSEEK_API_KEY from environment or .env file. Never hardcode.
"""

import json
import os
import sys
from typing import Any

import httpx

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_path = os.path.join(_project_root, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
_raw_base = os.environ.get("DEEPSEEK_API_BASE", os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
DEEPSEEK_BASE_URL = _raw_base.rstrip("/").removesuffix("/v1")


def _call_deepseek(
    prompt: str,
    model: str = "deepseek-reasoner",
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int = 8192,
) -> dict[str, Any]:
    if not DEEPSEEK_API_KEY:
        return {"error": "DEEPSEEK_API_KEY not set in environment"}

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = httpx.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        result: dict[str, Any] = {
            "content": choice["message"]["content"],
            "model": data.get("model", model),
            "usage": data.get("usage", {}),
        }
        reasoning = choice["message"].get("reasoning_content")
        if reasoning:
            result["reasoning"] = reasoning
        return result
    except httpx.HTTPStatusError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {exc.response.text[:500]}"}
    except Exception as exc:
        return {"error": str(exc)}


TOOLS = [
    {
        "name": "ask_deepseek",
        "description": (
            "Send a prompt to DeepSeek LLM. "
            "Use for: Chinese financial reasoning, factor expression generation, "
            "alternative perspectives, or tasks benefiting from DeepSeek Reasoner's chain-of-thought. "
            "Returns the model's response and optionally its reasoning trace."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The user prompt to send to DeepSeek",
                },
                "model": {
                    "type": "string",
                    "description": "Model name: 'deepseek-reasoner' (R1, default) or 'deepseek-chat' (V3)",
                    "default": "deepseek-reasoner",
                },
                "system": {
                    "type": "string",
                    "description": "Optional system prompt",
                    "default": "",
                },
                "temperature": {
                    "type": "number",
                    "description": "Sampling temperature (0-2)",
                    "default": 0.7,
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Max output tokens",
                    "default": 8192,
                },
            },
            "required": ["prompt"],
        },
    }
]


def _handle_request(req: dict) -> dict | None:
    method = req.get("method", "")
    rid = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "deepseek-mcp", "version": "1.0.0"},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        if tool_name == "ask_deepseek":
            result = _call_deepseek(
                prompt=args.get("prompt", ""),
                model=args.get("model", "deepseek-reasoner"),
                system=args.get("system", ""),
                temperature=args.get("temperature", 0.7),
                max_tokens=args.get("max_tokens", 8192),
            )
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}

    return {
        "jsonrpc": "2.0",
        "id": rid,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = _handle_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
