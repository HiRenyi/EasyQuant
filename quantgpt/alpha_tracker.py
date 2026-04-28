"""Track submitted alphas and check self-correlation before new submissions."""

import asyncio
import logging
import threading
import uuid as _uuid
from difflib import SequenceMatcher

from sqlalchemy import select

logger = logging.getLogger(__name__)


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


async def record_submitted_alpha(
    user_id: str,
    alpha_id: str,
    expression: str,
    region: str = "USA",
    universe: str = "TOP3000",
    delay: int = 1,
    decay: int = 0,
    neutralization: str = "SUBINDUSTRY",
    truncation: float = 0.08,
    sharpe: float | None = None,
    fitness: float | None = None,
    returns: float | None = None,
    turnover: float | None = None,
):
    from .db import _get_session_factory
    from .expression_parser import normalize_expression
    from .models import SubmittedAlpha

    normalized = normalize_expression(expression)
    uid = _uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    factory = _get_session_factory()

    async with factory() as session:
        try:
            record = SubmittedAlpha(
                user_id=uid,
                alpha_id=alpha_id,
                expression=expression,
                expression_normalized=normalized,
                region=region,
                universe=universe,
                delay=delay,
                decay=decay,
                neutralization=neutralization,
                truncation=truncation,
                sharpe=sharpe,
                fitness=fitness,
                returns=returns,
                turnover=turnover,
            )
            session.add(record)
            await session.commit()
            logger.info(f"Recorded submitted alpha: {alpha_id}")
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to record submitted alpha: {e}")


def record_submitted_alpha_sync(user_id: str, alpha_id: str, **kwargs):
    from . import task_store

    loop = task_store.main_loop
    if loop and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(
            record_submitted_alpha(user_id, alpha_id, **kwargs), loop,
        )
        try:
            future.result(timeout=15)
        except Exception as e:
            logger.error(f"Alpha tracking sync error: {e}")
    else:
        def _run():
            try:
                asyncio.run(record_submitted_alpha(user_id, alpha_id, **kwargs))
            except Exception as e:
                logger.error(f"Alpha tracking thread error: {e}")
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=10)


def compute_similarity(expr_a: str, expr_b: str) -> dict:
    from .expression_parser import extract_components, normalize_expression

    norm_a = normalize_expression(expr_a)
    norm_b = normalize_expression(expr_b)

    text_sim = SequenceMatcher(None, norm_a, norm_b).ratio()

    comp_a = extract_components(expr_a)
    comp_b = extract_components(expr_b)

    ops_a = set(comp_a.get("operators", []))
    ops_b = set(comp_b.get("operators", []))
    fields_a = set(comp_a.get("fields", []))
    fields_b = set(comp_b.get("fields", []))

    ops_jaccard = len(ops_a & ops_b) / len(ops_a | ops_b) if (ops_a | ops_b) else 1.0
    fields_jaccard = len(fields_a & fields_b) / len(fields_a | fields_b) if (fields_a | fields_b) else 1.0

    overall = 0.5 * text_sim + 0.3 * ops_jaccard + 0.2 * fields_jaccard

    return {
        "text_similarity": round(text_sim, 4),
        "operator_overlap": round(ops_jaccard, 4),
        "field_overlap": round(fields_jaccard, 4),
        "overall_similarity": round(overall, 4),
    }


async def check_self_correlation(
    user_id: str,
    expression: str,
    threshold: float = 0.85,
    session=None,
) -> dict:
    from .expression_parser import normalize_expression
    from .models import SubmittedAlpha

    uid = _uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    normalized = normalize_expression(expression)

    if session is not None:
        result = await session.execute(
            select(SubmittedAlpha).where(SubmittedAlpha.user_id == uid)
        )
        existing = result.scalars().all()
    else:
        from .db import _get_session_factory
        factory = _get_session_factory()
        async with factory() as _session:
            result = await _session.execute(
                select(SubmittedAlpha).where(SubmittedAlpha.user_id == uid)
            )
            existing = result.scalars().all()

    if not existing:
        return {"safe": True, "matches": [], "total_submitted": 0}

    matches = []
    for alpha in existing:
        if alpha.expression_normalized == normalized:
            matches.append({
                "alpha_id": alpha.alpha_id,
                "expression": alpha.expression,
                "similarity": compute_similarity(expression, alpha.expression),
                "exact_match": True,
                "region": alpha.region,
                "universe": alpha.universe,
                "fitness": alpha.fitness,
            })
            continue

        sim = compute_similarity(expression, alpha.expression)
        if sim["overall_similarity"] >= threshold:
            matches.append({
                "alpha_id": alpha.alpha_id,
                "expression": alpha.expression,
                "similarity": sim,
                "exact_match": False,
                "region": alpha.region,
                "universe": alpha.universe,
                "fitness": alpha.fitness,
            })

    matches.sort(key=lambda m: m["similarity"]["overall_similarity"], reverse=True)

    return {
        "safe": len(matches) == 0,
        "matches": matches[:10],
        "total_submitted": len(existing),
        "expression_normalized": normalized,
    }
