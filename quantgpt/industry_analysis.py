"""Industry-level factor signal computation for sector rotation analysis."""

import json
import logging

import numpy as np
import pandas as pd

from .expression_parser import parse_expression
from .factor_signals import (
    json_default,
    safe_apply_factor,
    sanitize_for_json,
    strip_outer_rank,
)

logger = logging.getLogger(__name__)

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


def compute_industry_signals(
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
            raw_expr = strip_outer_rank(expr)
            factor_func = parse_expression(raw_expr)
            market_df["_fv"] = safe_apply_factor(market_df, factor_func)

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
    return sanitize_for_json(json.loads(json.dumps(results, default=json_default)))
