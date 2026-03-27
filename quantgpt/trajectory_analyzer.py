"""Trajectory analyzer — compute quality metrics from iteration history.

Ported from XTQuant QuantaAlpha: orchestration/src/ai_runtime/evaluator/trajectory_analyzer.py
"""

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryMetrics:
    exploration_diversity: float  # CV of scores (0-1), high = diverse exploration
    convergence_rate: float      # slope of score trend (0-1), positive = improving
    stability_score: float       # consistency of scores (0-1), high = stable
    consecutive_declines: int    # number of consecutive score drops
    best_score: float
    best_expression: str
    num_iterations: int


def analyze_trajectory(iterations: list[dict]) -> TrajectoryMetrics:
    """Compute trajectory-level quality metrics from iteration history.

    Args:
        iterations: List of dicts with at least {expression, score}.
                    Ordered chronologically (oldest first).

    Returns:
        TrajectoryMetrics with computed indicators.
    """
    if not iterations:
        return TrajectoryMetrics(0, 0, 0, 0, 0, "", 0)

    scores = [it.get("score", 0) or 0 for it in iterations]
    n = len(scores)

    # Best
    best_idx = int(np.argmax(scores))
    best_score = scores[best_idx]
    best_expression = iterations[best_idx].get("expression", "")

    # Exploration diversity: coefficient of variation
    if n >= 2 and np.mean(scores) > 0:
        exploration_diversity = min(float(np.std(scores) / np.mean(scores)), 1.0)
    else:
        exploration_diversity = 0.0

    # Convergence rate: normalized linear regression slope
    if n >= 2:
        x = np.arange(n, dtype=float)
        slope = float(np.polyfit(x, scores, 1)[0])
        # Normalize: slope of 10 points/iteration → 1.0
        convergence_rate = max(0.0, min(slope / 10.0, 1.0))
    else:
        convergence_rate = 0.0

    # Stability: inverse of normalized volatility
    if n >= 2 and best_score > 0:
        volatility = float(np.std(scores)) / best_score
        stability_score = max(0.0, 1.0 - volatility)
    else:
        stability_score = 1.0

    # Consecutive declines from the end
    consecutive_declines = 0
    for i in range(n - 1, 0, -1):
        if scores[i] < scores[i - 1]:
            consecutive_declines += 1
        else:
            break

    return TrajectoryMetrics(
        exploration_diversity=round(exploration_diversity, 3),
        convergence_rate=round(convergence_rate, 3),
        stability_score=round(stability_score, 3),
        consecutive_declines=consecutive_declines,
        best_score=best_score,
        best_expression=best_expression,
        num_iterations=n,
    )
