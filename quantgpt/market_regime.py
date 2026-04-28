"""Market regime derivation from factor signals."""

import logging

import numpy as np

from .factor_signals import FactorSignal

logger = logging.getLogger(__name__)


def derive_market_regime(
    factor_signals: list[FactorSignal],
    index_changes: dict,
) -> dict:
    """Derive market regime from factor signals (not from price action).

    Returns dict with regime/style/risk_level/dominant_category/headline,
    stored directly in metrics JSON.
    """
    if not factor_signals:
        return {}

    # Group signals by category
    by_cat: dict[str, list[FactorSignal]] = {}
    for s in factor_signals:
        by_cat.setdefault(s.category, []).append(s)

    # --- Regime ---
    trend_signals = by_cat.get("trend", [])
    vol_signals = by_cat.get("volatility", [])
    trend_avg_strength = (
        np.mean([s.signal_strength for s in trend_signals]) if trend_signals else 0.0
    )
    trend_avg_pct = (
        np.mean([s.percentile_20d for s in trend_signals]) if trend_signals else 50.0
    )
    vol_avg_strength = (
        np.mean([s.signal_strength for s in vol_signals]) if vol_signals else 0.0
    )

    if trend_avg_strength >= 1.0 and trend_avg_pct >= 60:
        regime = "趋势市"
    elif vol_avg_strength <= -1.0:
        regime = "高波动"
    else:
        regime = "震荡市"

    # --- Style ---
    csi1000_chg = index_changes.get("csi1000_change", 0.0)
    hs300_chg = index_changes.get("hs300_change", 0.0)
    size_diff = csi1000_chg - hs300_chg
    if size_diff > 0.3:
        size_style = "小盘"
    elif size_diff < -0.3:
        size_style = "大盘"
    else:
        size_style = "均衡"

    # Momentum vs reversal — check trend factor direction
    momentum_count = sum(1 for s in trend_signals if s.direction == "转强")
    reversal_count = sum(1 for s in trend_signals if s.direction == "转弱")
    if momentum_count > reversal_count:
        driver = "动量驱动"
    elif reversal_count > momentum_count:
        driver = "反转驱动"
    else:
        driver = "均衡驱动"

    style = f"{size_style} · {driver}"

    # --- Risk level ---
    risk_score = 0
    total = len(factor_signals)
    down_count = sum(1 for s in factor_signals if s.direction == "转弱")
    if total > 0 and down_count / total >= 0.6:
        risk_score += 1
    # Volatility factors at low percentile = rising vol risk
    if vol_signals and np.mean([s.percentile_20d for s in vol_signals]) <= 30:
        risk_score += 1
    # High dispersion across many factors
    high_disp_count = sum(1 for s in factor_signals if s.dispersion == "高分化")
    if high_disp_count >= 3:
        risk_score += 1

    if risk_score >= 2:
        risk_level = "高"
    elif risk_score >= 1:
        risk_level = "中"
    else:
        risk_level = "低"

    # --- Dominant category ---
    cat_strengths = {}
    for cat, sigs in by_cat.items():
        cat_strengths[cat] = np.mean([abs(s.signal_strength) for s in sigs])
    dominant_category = max(cat_strengths, key=cat_strengths.get) if cat_strengths else "trend"

    # --- Headline ---
    risk_comment = {
        "低": "风险可控",
        "中": "短期波动风险上升",
        "高": "多因子共振预警",
    }.get(risk_level, "")
    headline = f"{size_style}{driver}{regime}，{risk_comment}"

    return {
        "regime": regime,
        "style": style,
        "risk_level": risk_level,
        "dominant_category": dominant_category,
        "headline": headline,
    }
