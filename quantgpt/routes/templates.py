"""Factor strategy templates — curated factor library."""

import json
from pathlib import Path
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1", tags=["templates"])

_TEMPLATES_FILE = Path(__file__).resolve().parent / "templates" / "factors.json"
_templates: list[dict] | None = None


def _load_templates() -> list[dict]:
    global _templates
    if _templates is None:
        with open(_TEMPLATES_FILE, encoding="utf-8") as f:
            _templates = json.load(f)
    return _templates


@router.get("/templates")
async def list_templates(
    category: str | None = Query(None, description="按类别筛选: momentum/value/volume/volatility/technical/composite"),
    difficulty: str | None = Query(None, description="按难度筛选: beginner/intermediate/advanced"),
):
    """获取因子策略模板列表。"""
    templates = _load_templates()
    result = templates

    if category:
        result = [t for t in result if t["category"] == category]
    if difficulty:
        result = [t for t in result if t["difficulty"] == difficulty]

    return {"templates": result, "total": len(result)}
