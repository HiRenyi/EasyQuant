"""Daily market summary — factor-driven post-market analysis.

Pipeline:
1. Fetch market data (hs300 stocks, last 70 days) + benchmark returns
2. Compute factor signals from 15 core factor templates
3. Build rich LLM prompt with real factor data
4. Generate markdown report via DeepSeek
5. Store to DB
"""

import json
import logging
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from openai import OpenAI

from .expression_parser import parse_expression
from .market_data import MarketDataFetcher, fetch_benchmark_returns, get_universe

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_PATH = Path(__file__).resolve().parent / "templates" / "factors.json"


def _json_default(obj):
    """Convert numpy types to native Python for JSON serialization."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        if np.isnan(v) or np.isinf(v):
            return None
        return v
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _sanitize_for_json(obj):
    """Recursively replace NaN/Inf with None for JSON compatibility."""
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    return obj

_DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
_DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
_DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# ─── Factor signal computation ───────────────────────────────────


@dataclass
class FactorSignal:
    factor_id: str
    factor_name: str
    category: str
    signal_description: str
    direction: str          # "转强" | "转弱" | "持平"
    dispersion: str         # "高分化" | "中等" | "低分化"
    top_stocks: list        # [(code, value), ...]
    bottom_stocks: list     # [(code, value), ...]
    today_mean: float
    yesterday_mean: float
    # Percentile stats for compliant reporting
    pct_above_median: float  # % of stocks above cross-sectional median
    top10_pct_change: float  # avg change of top 10% vs yesterday
    # Historical context (20-day rolling window)
    percentile_20d: float   # today's mean percentile among recent 20-day means (0-100)
    zscore_20d: float       # (today_mean - 20d_mean_avg) / 20d_mean_std
    signal_strength: int    # -2 to +2 composite: direction + percentile


def _load_factor_templates() -> list:
    """Load factor templates from JSON."""
    with open(_TEMPLATES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_apply_factor(df: pd.DataFrame, factor_func) -> pd.Series:
    """Apply factor function to a DataFrame, returning NaN on error."""
    try:
        result = factor_func(df)
        if isinstance(result, pd.Series):
            result.index = df.index
        return result
    except Exception:
        return pd.Series(np.nan, index=df.index)


def _strip_outer_rank(expression: str) -> str:
    """Remove outer rank() wrapper from expression for signal analysis.

    rank() normalizes values to [0, 1] percentiles, making cross-sectional
    means ~0.5 every day. For day-over-day signal detection we need raw values.
    Examples:
        "rank(close/ts_mean(close,20))" -> "close/ts_mean(close,20)"
        "rank(-1 * x) - rank(y)"        -> "rank(-1 * x) - rank(y)"  (not simple wrapper)
    """
    stripped = expression.strip()
    if not stripped.startswith("rank("):
        return expression
    # Check if the entire expression is rank(...) by matching parentheses
    depth = 0
    for i, ch in enumerate(stripped):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                # If we're at the end, the whole thing is rank(...)
                if i == len(stripped) - 1:
                    return stripped[5:i]  # strip "rank(" and ")"
                else:
                    return expression  # rank(...) is only part of expr
    return expression


def _compute_factor_signals(
    market_df: pd.DataFrame,
    templates: list,
) -> List[FactorSignal]:
    """Compute factor signals for each template on today's market data.

    Requires market_df to have at least 70 days of history for time-series
    operators. Extracts today vs yesterday cross-sectional stats.
    """
    market_df = market_df.copy()
    market_df["trade_date"] = pd.to_datetime(market_df["trade_date"])
    market_df = market_df.sort_values(["stock_code", "trade_date"])

    all_dates = sorted(market_df["trade_date"].unique())
    if len(all_dates) < 2:
        logger.warning("Not enough trading days for factor signal computation")
        return []

    today = all_dates[-1]
    yesterday = all_dates[-2]

    signals = []
    for tmpl in templates:
        try:
            # Strip outer rank() for signal analysis — rank() normalizes to
            # ~0.5 mean every day, hiding real cross-sectional changes.
            # Raw factor values are needed to detect day-over-day shifts.
            expr = tmpl["expression"]
            raw_expr = _strip_outer_rank(expr)
            factor_func = parse_expression(raw_expr)
            market_df["_fv"] = _safe_apply_factor(market_df, factor_func)

            # Today's cross-section
            today_mask = market_df["trade_date"] == today
            today_df = market_df.loc[today_mask, ["stock_code", "_fv"]].dropna(subset=["_fv"])

            yesterday_mask = market_df["trade_date"] == yesterday
            yesterday_df = market_df.loc[yesterday_mask, ["stock_code", "_fv"]].dropna(subset=["_fv"])

            if len(today_df) < 10 or len(yesterday_df) < 10:
                continue

            today_mean = float(today_df["_fv"].mean())
            yesterday_mean = float(yesterday_df["_fv"].mean())
            today_std = float(today_df["_fv"].std())
            today_median = float(today_df["_fv"].median())

            # Direction
            delta = today_mean - yesterday_mean
            threshold = 0.05 * today_std if today_std > 0 else 0.001
            if delta > threshold:
                direction = "转强"
            elif delta < -threshold:
                direction = "转弱"
            else:
                direction = "持平"

            # Dispersion — compare today's cross-sectional std to recent average
            # Also collect daily cross-sectional means for percentile/z-score
            recent_stds = []
            recent_means = []
            for d in all_dates[-20:]:
                d_mask = market_df["trade_date"] == d
                d_vals = market_df.loc[d_mask, "_fv"].dropna()
                d_std = d_vals.std()
                d_mean = d_vals.mean()
                if not np.isnan(d_std):
                    recent_stds.append(d_std)
                if not np.isnan(d_mean):
                    recent_means.append(float(d_mean))
            avg_std = np.mean(recent_stds) if recent_stds else today_std
            if avg_std > 0 and today_std > 1.2 * avg_std:
                dispersion = "高分化"
            elif avg_std > 0 and today_std < 0.8 * avg_std:
                dispersion = "低分化"
            else:
                dispersion = "中等"

            # 20-day percentile and z-score of today's cross-sectional mean
            if len(recent_means) >= 3:
                mean_arr = np.array(recent_means)
                mean_avg = float(np.mean(mean_arr))
                mean_std = float(np.std(mean_arr, ddof=1))
                # Percentile: fraction of historical means <= today_mean
                percentile_20d = round(float(np.sum(mean_arr <= today_mean) / len(mean_arr)) * 100, 1)
                zscore_20d = round((today_mean - mean_avg) / mean_std, 2) if mean_std > 0 else 0.0
            else:
                percentile_20d = 50.0
                zscore_20d = 0.0

            # Signal strength: composite of direction + percentile
            if direction == "转强":
                signal_strength = 2 if percentile_20d >= 75 else 1
            elif direction == "转弱":
                signal_strength = -2 if percentile_20d <= 25 else -1
            else:
                signal_strength = 0

            # Percentile stats for compliant reporting
            pct_above_median = round(float((today_df["_fv"] > today_median).mean()) * 100, 1)

            # Top 10% group average change
            n_top = max(1, len(today_df) // 10)
            sorted_today = today_df.sort_values("_fv", ascending=False)
            top_codes = set(sorted_today.head(n_top)["stock_code"])
            top_today_avg = sorted_today.head(n_top)["_fv"].mean()
            top_yest = yesterday_df[yesterday_df["stock_code"].isin(top_codes)]["_fv"].mean()
            top10_pct_change = round(float(top_today_avg - top_yest), 4) if not np.isnan(top_yest) else 0.0

            # Top / bottom stocks (for signal cards, not for LLM)
            top_stocks = [
                (row["stock_code"], round(float(row["_fv"]), 4))
                for _, row in sorted_today.head(3).iterrows()
            ]
            bottom_stocks = [
                (row["stock_code"], round(float(row["_fv"]), 4))
                for _, row in sorted_today.tail(3).iterrows()
            ]

            signals.append(FactorSignal(
                factor_id=tmpl["id"],
                factor_name=tmpl["name"],
                category=tmpl["category"],
                signal_description=tmpl.get("signal_description", ""),
                direction=direction,
                dispersion=dispersion,
                top_stocks=top_stocks,
                bottom_stocks=bottom_stocks,
                today_mean=round(today_mean, 6),
                yesterday_mean=round(yesterday_mean, 6),
                pct_above_median=pct_above_median,
                top10_pct_change=top10_pct_change,
                percentile_20d=percentile_20d,
                zscore_20d=zscore_20d,
                signal_strength=signal_strength,
            ))
        except Exception as e:
            logger.warning(f"Factor signal computation failed for {tmpl['id']}: {e}")

    # Clean up temp column
    if "_fv" in market_df.columns:
        market_df.drop(columns=["_fv"], inplace=True)

    return signals


# ─── Industry-level signal computation ───────────────────────────

# Map verbose CSRC industry names to short display names
_INDUSTRY_SHORT_NAMES = {
    "C39计算机、通信和其他电子设备制造业": "电子",
    "J66货币金融服务": "银行",
    "C38电气机械和器材制造业": "电力设备",
    "J67资本市场服务": "券商",
    "C27医药制造业": "医药",
    "C26化学原料和化学制品制造业": "化工",
    "C35专用设备制造业": "机械",
    "C15酒、饮料和精制茶制造业": "食品饮料",
    "I65软件和信息技术服务业": "计算机",
    "C36汽车制造业": "汽车",
    "D44电力、热力生产和供应业": "公用事业",
    "E48土木工程建筑业": "建筑",
    "C32有色金属冶炼和压延加工业": "有色金属",
    "C30非金属矿物制品业": "建材",
    "K70房地产业": "房地产",
    "J68保险业": "保险",
    "C37铁路、船舶、航空航天和其他运输设备制造业": "军工",
    "G56航空运输业": "航空",
    "B06煤炭开采和洗选业": "煤炭",
    "I64互联网和相关服务": "互联网",
    "I63电信、广播电视和卫星传输服务": "通信",
    "C13农副食品加工业": "农业",
    "B09有色金属矿采选业": "矿业",
    "C31黑色金属冶炼和压延加工业": "钢铁",
    "C29橡胶和塑料制品业": "化纤",
    "C28化学纤维制造业": "纺织",
    "M73研究和试验发展": "科研",
    "Q84卫生": "医疗",
    "C34通用设备制造业": "通用设备",
    "B07石油和天然气开采业": "石油",
    "G54道路运输业": "交运",
    "R86广播、电视、电影和录音制作业": "传媒",
    "C14食品制造业": "食品",
    "C33金属制品业": "金属制品",
    "N77生态保护和环境治理业": "环保",
    "F51批发业": "商贸",
    "F52零售业": "零售",
    "L72商务服务业": "商务服务",
    "G55水上运输业": "航运",
}


def _shorten_industry_name(name: str) -> str:
    """Convert verbose CSRC industry name to short display name."""
    return _INDUSTRY_SHORT_NAMES.get(name, name)


def _compute_industry_signals(
    market_df: pd.DataFrame,
    templates: list,
) -> list[dict]:
    """Compute per-industry factor signals for sector rotation analysis.

    For each factor template, computes the industry-level mean of raw factor
    values on the latest trading day, then ranks industries across all factors
    to produce a composite score.

    Returns a list of dicts sorted by composite_score descending, each with:
        industry, stock_count, composite_score, direction, factor_details, top_factors
    """
    from .neutralize import get_industry_data

    market_df = market_df.copy()
    market_df["trade_date"] = pd.to_datetime(market_df["trade_date"])
    market_df = market_df.sort_values(["stock_code", "trade_date"])

    all_dates = sorted(market_df["trade_date"].unique())
    if len(all_dates) < 2:
        return []

    today = all_dates[-1]
    yesterday = all_dates[-2]

    # Get industry classification
    stock_codes = market_df["stock_code"].unique().tolist()
    ind_data = get_industry_data(stock_codes)
    if ind_data is None or len(ind_data) == 0:
        logger.warning("[industry_signals] No industry data available")
        return []

    # Merge industry into market_df
    market_df = market_df.merge(
        ind_data[["stock_code", "industry"]], on="stock_code", how="left"
    )
    market_df["industry"] = market_df["industry"].fillna("其他")

    # Compute per-industry factor means for today and yesterday
    industry_records: dict[str, dict] = {}  # industry -> {factor_details, ...}

    for tmpl in templates:
        try:
            expr = tmpl["expression"]
            raw_expr = _strip_outer_rank(expr)
            factor_func = parse_expression(raw_expr)
            market_df["_fv"] = _safe_apply_factor(market_df, factor_func)

            for day_label, day_date in [("today", today), ("yesterday", yesterday)]:
                day_df = market_df.loc[
                    market_df["trade_date"] == day_date,
                    ["stock_code", "industry", "_fv"],
                ].dropna(subset=["_fv"])

                if len(day_df) < 10:
                    continue

                ind_means = day_df.groupby("industry")["_fv"].mean()
                for ind_name, mean_val in ind_means.items():
                    if ind_name not in industry_records:
                        industry_records[ind_name] = {
                            "factor_details": {},
                            "stock_count": 0,
                        }
                    fid = tmpl["id"]
                    if fid not in industry_records[ind_name]["factor_details"]:
                        industry_records[ind_name]["factor_details"][fid] = {
                            "name": tmpl["name"],
                        }
                    industry_records[ind_name]["factor_details"][fid][
                        f"{day_label}_mean"
                    ] = round(float(mean_val), 6)

            # Count stocks per industry (today only)
            today_df = market_df.loc[
                market_df["trade_date"] == today,
                ["stock_code", "industry"],
            ]
            for ind_name, cnt in today_df.groupby("industry").size().items():
                if ind_name in industry_records:
                    industry_records[ind_name]["stock_count"] = int(cnt)

        except Exception as e:
            logger.warning(f"[industry_signals] Factor {tmpl['id']} failed: {e}")

    if "_fv" in market_df.columns:
        market_df.drop(columns=["_fv"], inplace=True)

    if not industry_records:
        return []

    # Rank industries per factor and compute composite score
    # For each factor, rank industries by today_mean (higher = stronger)
    factor_ids = list({
        fid
        for rec in industry_records.values()
        for fid in rec["factor_details"]
    })
    industries = list(industry_records.keys())

    # Build matrix: rows=industries, cols=factors, values=today_mean
    for fid in factor_ids:
        vals = {}
        for ind in industries:
            fd = industry_records[ind]["factor_details"].get(fid, {})
            vals[ind] = fd.get("today_mean", np.nan)

        # Rank across industries (percentile rank 0-1)
        series = pd.Series(vals)
        ranked = series.rank(pct=True, na_option="keep")
        for ind in industries:
            fd = industry_records[ind]["factor_details"].get(fid)
            if fd:
                fd["rank"] = round(float(ranked.get(ind, 0.5)), 3)

    # Composite score: average rank across all factors, scaled to [-2, +2]
    results = []
    for ind in industries:
        rec = industry_records[ind]
        if rec["stock_count"] < 3:
            continue  # skip tiny industries

        ranks = [
            fd["rank"]
            for fd in rec["factor_details"].values()
            if "rank" in fd and not np.isnan(fd["rank"])
        ]
        if not ranks:
            continue

        avg_rank = float(np.mean(ranks))
        # Scale: 0.5 = neutral, map to [-2, +2]
        composite = round((avg_rank - 0.5) * 4, 2)

        # Direction
        if composite > 0.2:
            direction = "偏强"
        elif composite < -0.2:
            direction = "偏弱"
        else:
            direction = "中性"

        # Top factors: sort by rank, pick top 3 most extreme
        factor_list = []
        for fid, fd in rec["factor_details"].items():
            if "rank" not in fd:
                continue
            deviation = fd["rank"] - 0.5
            today_val = fd.get("today_mean", 0)
            yest_val = fd.get("yesterday_mean", 0)
            change = today_val - yest_val if yest_val else 0
            factor_list.append({
                "id": fid,
                "name": fd["name"],
                "rank": fd["rank"],
                "deviation": round(deviation, 3),
                "today_mean": today_val,
                "change": round(change, 6),
            })
        factor_list.sort(key=lambda x: abs(x["deviation"]), reverse=True)
        top_factors = factor_list[:3]

        results.append({
            "industry": _shorten_industry_name(ind),
            "stock_count": rec["stock_count"],
            "composite_score": composite,
            "direction": direction,
            "top_factors": top_factors,
            "factor_details": {
                fid: {
                    "name": fd["name"],
                    "rank": fd.get("rank", 0.5),
                    "today_mean": fd.get("today_mean", 0),
                    "yesterday_mean": fd.get("yesterday_mean", 0),
                }
                for fid, fd in rec["factor_details"].items()
            },
        })

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    logger.info(
        f"[industry_signals] Computed signals for {len(results)} industries"
    )
    return _sanitize_for_json(json.loads(json.dumps(results, default=_json_default)))


# ─── Benchmark index changes ─────────────────────────────────────


def _get_today_index_changes(date: str | None = None) -> dict:
    """Fetch benchmark index changes for a given date."""
    today = date or datetime.now().strftime("%Y-%m-%d")
    start = (pd.Timestamp(today) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")

    metrics = {}
    for name, code in [("hs300", "hs300"), ("sz50", "sz50"), ("zz500", "zz500"), ("csi1000", "csi1000")]:
        try:
            ret = fetch_benchmark_returns(code, start, today)
            if ret is not None and len(ret) > 0:
                latest = ret.iloc[-1]
                metrics[f"{name}_change"] = round(float(latest) * 100, 2)
            else:
                metrics[f"{name}_change"] = 0.0
        except Exception as e:
            logger.warning(f"Failed to fetch {name} returns: {e}")
            metrics[f"{name}_change"] = 0.0

    return metrics


# ─── Market regime derivation ────────────────────────────────────


def _derive_market_regime(
    factor_signals: List[FactorSignal],
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


# ─── LLM prompt building ─────────────────────────────────────────


_CATEGORY_NAMES = {
    "trend": "趋势类",
    "volume": "量价类",
    "volatility": "波动类",
    "technical": "技术类",
    "valuation": "估值类",
}

_SYSTEM_PROMPT = """你是一位资深量化策略师，擅长用因子模型刻画市场结构，并从散户、游资、机构三种视角解读市场行为。

## 核心原则

1. **因子驱动**：所有结论必须基于因子信号数据，禁止凭空推测。
2. **先结论后展开**：每个章节开头用 1-2 句加粗文字给出该段核心结论，方便快速阅读。
3. **因子→经济含义→操作建议**：每个因子不只报数字，要解读"这意味着什么"。
4. **多角色视角**：从散户（情绪/追涨杀跌）、游资（短线博弈/题材轮动）、机构（风格切换/配置调整）角度分析。

## 排版规范（极其重要，必须严格遵守）

1. **每个 ## 大标题前后必须有一个空行**
2. **每个 ### 小标题前后必须有一个空行**
3. **每个 • 或 - 项目符号条目必须独占一行，条目之间用空行分隔**
4. **段落之间必须有空行，禁止文字紧贴**
5. 不要用 • 符号，统一用 Markdown 的 - 项目符号
6. 每个因子解读必须独占一段，格式为：`- **因子名（方向）：** 解读内容`，每个因子之间空一行

## 严格要求

1. 直接输出正文，第一行必须是 `#` 标题，禁止任何开场白（"好的""根据"等）
2. 严禁出现任何个股代码或个股名称，只能用"多头组Top 10%""分位90%"等分组表达
3. 使用 **加粗** 突出关键数字和结论
4. 每个因子的解读必须用 Markdown 无序列表（`- ` 开头），禁止直接写成段落
5. 字数控制在 1500-2200 字
6. 不要编造数据中没有的信息
7. 重点解读分位数异常（>80 或 <20）和 Z-Score 异常（|z|>1.5）的因子
8. 行业轮动分析必须基于提供的行业因子数据，给出具体行业名称和因子逻辑
9. 报告末尾必须有总结+投资建议+免责声明"""


def _build_llm_prompt(
    date: str,
    index_changes: dict,
    factor_signals: List[FactorSignal],
    regime_data: dict | None = None,
    industry_signals: list[dict] | None = None,
) -> str:
    """Build a rich LLM prompt with real factor data (no individual stock codes)."""
    lines = [f"今日日期：{date}\n"]

    # Market regime context (computed from factors, not price)
    if regime_data:
        lines.append("## 市场状态（由因子信号推导，非价格反推）\n")
        lines.append(f"- **Regime**: {regime_data.get('regime', '未知')}")
        lines.append(f"- **风格**: {regime_data.get('style', '未知')}")
        lines.append(f"- **风险等级**: {regime_data.get('risk_level', '未知')}")
        lines.append(f"- **一句话**: {regime_data.get('headline', '')}")
        lines.append("")

    # Index changes
    lines.append("## 大盘数据\n")
    lines.append("| 指数 | 涨跌幅 |")
    lines.append("|------|--------|")
    lines.append(f"| 沪深300 | {index_changes.get('hs300_change', 0)}% |")
    lines.append(f"| 上证50 | {index_changes.get('sz50_change', 0)}% |")
    lines.append(f"| 中证500 | {index_changes.get('zz500_change', 0)}% |")
    lines.append(f"| 中证1000 | {index_changes.get('csi1000_change', 0)}% |")
    lines.append("")

    # Factor signal summary
    up_count = sum(1 for s in factor_signals if s.direction == "转强")
    down_count = sum(1 for s in factor_signals if s.direction == "转弱")
    flat_count = sum(1 for s in factor_signals if s.direction == "持平")
    lines.append(f"## 因子信号总览（基于沪深300成分股）\n")
    lines.append(f"**{up_count}** 个因子转强，**{down_count}** 个转弱，**{flat_count}** 个持平\n")

    # Factor signals grouped by category — NO individual stock codes
    category_order = ["trend", "volume", "volatility", "technical", "valuation"]
    for cat in category_order:
        cat_signals = [s for s in factor_signals if s.category == cat]
        if not cat_signals:
            continue

        lines.append(f"### {_CATEGORY_NAMES.get(cat, cat)}")
        for s in cat_signals:
            lines.append(
                f"- **{s.factor_name}** [{s.direction}] 强度{s.signal_strength:+d}，"
                f"20日分位{s.percentile_20d:.0f}%，Z-Score={s.zscore_20d:+.2f}，"
                f"分化度[{s.dispersion}]，"
                f"多头组Top10%日均变化{s.top10_pct_change:+.4f}，"
                f"{s.pct_above_median}%标的高于中位数。"
                f"{s.signal_description}"
            )
        lines.append("")

    # Industry rotation signals
    if industry_signals:
        n_top = min(5, len(industry_signals))
        n_bot = min(5, len(industry_signals))
        top_industries = industry_signals[:n_top]
        bottom_industries = industry_signals[-n_bot:]

        lines.append("## 行业轮动信号（基于沪深300成分股，申万一级行业）\n")

        lines.append("### 强势行业（综合因子得分 Top 5）")
        for ind in top_industries:
            factors_str = "、".join(
                f"{f['name']}({f['today_mean'] or 0:+.4f})"
                for f in ind["top_factors"][:3]
            )
            lines.append(
                f"- **{ind['industry']}**（{ind['stock_count']}只）"
                f"综合得分{ind['composite_score']:+.2f}[{ind['direction']}]："
                f"{factors_str}"
            )
        lines.append("")

        lines.append("### 弱势行业（综合因子得分 Bottom 5）")
        for ind in reversed(bottom_industries):
            factors_str = "、".join(
                f"{f['name']}({f['today_mean'] or 0:+.4f})"
                for f in ind["top_factors"][:3]
            )
            lines.append(
                f"- **{ind['industry']}**（{ind['stock_count']}只）"
                f"综合得分{ind['composite_score']:+.2f}[{ind['direction']}]："
                f"{factors_str}"
            )
        lines.append("")

    # Writing instructions
    lines.append("## 输出格式要求\n")
    lines.append("严格按以下结构输出，不要有任何开场白：\n")
    lines.append(f"# A股市场因子研究日报 | {date}\n")
    lines.append("## 一、市场全景解读\n")
    lines.append('**开头用 1-2 句加粗文字给出今日市场核心特征**（如\u201c这是一个典型的小盘风格占优交易日\u201d）。\n')
    lines.append("然后用编号列表展开：")
    lines.append("1. 行情特征：指数排序（如 中证1000 > 中证500 > 沪深300），说明大小盘分化")
    lines.append("2. 解读：结合趋势因子方向，判断市场风险偏好（Risk-on/Risk-off）")
    lines.append("3. 资金面：结合量价因子判断资金活跃度和流向\n")

    lines.append("## 二、核心因子信号深度拆解\n")
    lines.append('**开头用 1 句话概括因子信号全貌**（如\u201c本报告通过X个维度监测了市场背后的逻辑\u201d）\n')
    lines.append("按类别逐一解读，每个类别：")
    lines.append("1. 类别小标题用 `### 1. 趋势类：xxx` 格式，冒号后用 3-5 字概括该类因子传递的信号")
    lines.append("2. 每个因子必须用 Markdown 列表格式（`- `开头），每个因子独占一段，格式：")
    lines.append("   `- **因子名（方向）：** 经济含义解读`")
    lines.append('   - 不只报数字，要解释\u201c这意味着什么\u201d')
    lines.append("   - 例：")
    lines.append('   - **20日动量（转强）：** 意味着\u201c强者恒强\u201d。加速动量显著转强(+0.27)，说明市场不仅在涨，涨速还在加快，这是情绪进入高潮的标志。')
    lines.append('   - 例：**5日反转（转弱）：** 意味着跌了去抄底的逻辑行不通了，现在的市场逻辑是\u201c追高\u201d。')
    lines.append("3. 每类因子解读完后，用 1 句话总结该类因子传递的整体信号\n")

    lines.append("## 三、参与者行为画像\n")
    lines.append("**开头用 1 句话概括当前市场的参与者结构**\n")
    lines.append("从三个角度分析：")
    lines.append("1. **散户视角**：基于动量/反转因子判断追涨杀跌情绪，换手率异动判断散户参与热度")
    lines.append("2. **游资视角**：基于成交量异动+日内动量判断短线博弈强度，高分化因子判断题材轮动")
    lines.append("3. **机构视角**：基于低波动+均线偏离+估值因子判断机构风格切换和配置调整\n")

    if industry_signals:
        lines.append("## 四、行业轮动与板块建议\n")
        lines.append("**开头用 1 句话概括今日行业轮动格局**\n")
        lines.append("基于上方提供的行业因子数据，分析：")
        lines.append("1. **强势板块解读**：逐一解读 Top 3-5 强势行业，说明哪些因子驱动了该行业走强，经济含义是什么")
        lines.append("2. **弱势板块解读**：逐一解读 Bottom 3-5 弱势行业，说明弱势原因")
        lines.append("3. **板块轮动建议**：基于因子信号给出 2-3 条具体的板块配置建议")
        lines.append("   - 例：**关注电子板块：** 动量转强+成交量异动+价格突破三因子共振，资金持续流入")
        lines.append("   - 例：**回避银行板块：** 低波动因子偏弱+动量转弱，机构可能在减配\n")

        lines.append("## 五、总结与操作建议\n")
    else:
        lines.append("## 四、总结与操作建议\n")
    lines.append("### 1. 核心结论")
    lines.append('用 2-3 句话总结今日市场全貌，提炼关键词（如\u201c情绪驱动\u201d\u201c中小盘领头\u201d\u201c动能加速\u201d等）\n')
    lines.append("### 2. 投资建议")
    lines.append("用项目符号列出 3-4 条**基于因子逻辑的具体建议**：")
    lines.append("- 每条建议格式：**建议标题：** 具体说明 + 因子逻辑支撑")
    lines.append("- 例：**不要轻易抄底：** 因为反转因子转弱，之前热度较高的股票跌下去后短期内起不来。")
    lines.append("- 例：**关注低位补涨：** 换手率反转因子转强提示，寻找处于底部、近期刚开始活跃的中小市值品种。")
    lines.append("- 例：**注意止盈：** 均线偏离度显示超买，不建议此时大幅加仓，应在普涨中逐步兑现远离均线的盈利筹码。\n")

    lines.append("---")
    lines.append("*本内容基于量化因子模型与历史数据分析，仅供研究参考，不构成任何投资建议。市场有风险，投资需谨慎。*")

    return "\n".join(lines)


# ─── LLM call ─────────────────────────────────────────────────────


def _call_llm(prompt: str) -> str:
    """Call DeepSeek LLM for market summary."""
    client = OpenAI(api_key=_DEEPSEEK_API_KEY, base_url=_DEEPSEEK_BASE_URL)
    resp = client.chat.completions.create(
        model=_DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=4000,
    )
    text = resp.choices[0].message.content.strip()

    # Strip any preamble before the first markdown heading
    match = re.search(r'^(#{1,3}\s)', text, re.MULTILINE)
    if match and match.start() > 0:
        text = text[match.start():]

    # Post-process: ensure blank lines around headings and between list items
    text = _fix_markdown_spacing(text)

    return text


def _fix_markdown_spacing(text: str) -> str:
    """Ensure proper blank lines in markdown output for readable rendering."""
    lines = text.split("\n")
    result = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        prev_stripped = result[-1].strip() if result else ""

        # Ensure blank line before headings (# ## ###)
        if stripped.startswith("#") and prev_stripped and not prev_stripped == "":
            result.append("")

        result.append(line)

        # Ensure blank line after headings
        if stripped.startswith("#") and i + 1 < len(lines) and lines[i + 1].strip():
            result.append("")

    text = "\n".join(result)

    # Collapse 3+ consecutive blank lines to 2
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    return text


# ─── Main pipeline ────────────────────────────────────────────────


async def generate_daily_summary(db, market: str = "a_share", date: str | None = None) -> dict | None:
    """Generate and store daily market summary using factor signals.

    Args:
        db: async DB session.
        market: "a_share" or "crypto".
        date: target date "YYYY-MM-DD". Defaults to today.

    Returns the summary dict or None if already exists for that date.
    """
    from .models import DailySummary
    from sqlalchemy import select
    import uuid

    today = date or datetime.now().strftime("%Y-%m-%d")

    # Check if already generated
    existing = await db.execute(
        select(DailySummary).where(
            DailySummary.date == today,
            DailySummary.market == market,
        )
    )
    if existing.scalar_one_or_none():
        logger.info(f"Daily summary for {today} ({market}) already exists, skipping")
        return None

    logger.info(f"[daily_summary] Starting factor-driven summary for {today} ({market})")

    # Step 1: Get index changes
    index_changes = _get_today_index_changes(today)
    logger.info(f"[daily_summary] Index changes: {index_changes}")

    # Step 2: Load market data for factor computation (last 70 trading days)
    start_date = (pd.Timestamp(today) - pd.Timedelta(days=100)).strftime("%Y-%m-%d")
    try:
        stock_codes = get_universe("hs300", date=today)
        fetcher = MarketDataFetcher()
        market_df = fetcher.fetch_stocks(stock_codes, start_date, today)
    except Exception as e:
        logger.error(f"[daily_summary] Failed to fetch market data: {e}")
        market_df = None

    # Step 3: Load templates and compute factor signals
    factor_signals = []
    if market_df is not None and len(market_df) > 0:
        templates = _load_factor_templates()

        # Check if valuation factors need fundamental data
        valuation_templates = [t for t in templates if t["category"] == "valuation"]
        if valuation_templates:
            try:
                from .fundamental_data import enrich_with_fundamentals_rq, detect_fundamental_vars
                all_fund_vars = set()
                for t in valuation_templates:
                    all_fund_vars |= detect_fundamental_vars(t["expression"])
                if all_fund_vars:
                    enriched = enrich_with_fundamentals_rq(
                        market_df, all_fund_vars, stock_codes, start_date, today
                    )
                    if enriched is not None:
                        market_df = enriched
                        logger.info(f"[daily_summary] Enriched with fundamentals: {all_fund_vars}")
                    else:
                        logger.warning("[daily_summary] Fundamental data unavailable, skipping valuation factors")
                        templates = [t for t in templates if t["category"] != "valuation"]
            except Exception as e:
                logger.warning(f"[daily_summary] Fundamental enrichment failed: {e}")
                templates = [t for t in templates if t["category"] != "valuation"]

        factor_signals = _compute_factor_signals(market_df, templates)
        logger.info(f"[daily_summary] Computed {len(factor_signals)} factor signals")
    else:
        logger.warning("[daily_summary] No market data, generating summary with index data only")

    # Step 3b: Compute industry-level signals
    industry_signals = []
    if market_df is not None and len(market_df) > 0 and templates:
        try:
            industry_signals = _compute_industry_signals(market_df, templates)
        except Exception as e:
            logger.warning(f"[daily_summary] Industry signal computation failed: {e}")

    # Step 4: Derive market regime from factor signals
    regime_data = _derive_market_regime(factor_signals, index_changes)
    if regime_data:
        logger.info(f"[daily_summary] Regime: {regime_data.get('headline', '')}")

    # Step 5: Build prompt and call LLM
    prompt = _build_llm_prompt(today, index_changes, factor_signals, regime_data, industry_signals)
    logger.info(f"[daily_summary] LLM prompt: {len(prompt)} chars, calling DeepSeek...")
    content = _call_llm(prompt)
    logger.info(f"[daily_summary] LLM response: {len(content)} chars")

    # Step 6: Store in DB
    metrics = {
        **index_changes,
        **regime_data,
        "factor_signals": [asdict(s) for s in factor_signals],
        "factor_count": len(factor_signals),
        "industry_signals": industry_signals,
    }

    summary = DailySummary(
        id=uuid.uuid4(),
        date=today,
        market=market,
        title=f"{today} A股盘后总结",
        content=content,
        metrics=metrics,
        created_at=datetime.now(timezone.utc),
    )
    db.add(summary)
    await db.commit()

    logger.info(f"[daily_summary] Summary for {today} saved successfully")
    return {
        "id": str(summary.id),
        "date": summary.date,
        "title": summary.title,
        "content": summary.content,
        "metrics": summary.metrics,
    }
