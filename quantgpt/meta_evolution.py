"""Meta-evolution strategy selector — adaptive strategy based on trajectory.

Ported from XTQuant QuantaAlpha: orchestration/src/ai_runtime/agent/meta_evolution.py
"""

import logging
from enum import Enum

from .trajectory_analyzer import TrajectoryMetrics

logger = logging.getLogger(__name__)


class EvolutionStrategy(Enum):
    EXPLOIT = "exploit"        # Refine current best via targeted mutation
    EXPLORE = "explore"        # Try completely different approach
    RECOMBINE = "recombine"    # Crossover from historical high-scorers
    SIMPLIFY = "simplify"      # Reduce complexity


def select_strategy(
    metrics: TrajectoryMetrics,
    current_score: float,
    nesting_depth: int = 0,
) -> EvolutionStrategy:
    """Select evolution strategy based on trajectory characteristics.

    Decision tree (ordered by priority):
    1. Complexity too high → SIMPLIFY
    2. High score + low diversity → EXPLOIT (refine)
    3. Plateaued (2+ declines, ≥3 iterations) → RECOMBINE
    4. Low score + early stage → EXPLORE (restart)
    5. High diversity + low convergence → EXPLORE
    6. Medium score + stable → EXPLOIT
    7. Default → EXPLOIT
    """
    n = metrics.num_iterations
    diversity = metrics.exploration_diversity
    convergence = metrics.convergence_rate
    stability = metrics.stability_score
    declines = metrics.consecutive_declines

    # 1. Complexity penalty
    if nesting_depth > 8:
        logger.info(f"[meta_evolution] strategy=SIMPLIFY (nesting={nesting_depth})")
        return EvolutionStrategy.SIMPLIFY

    # 2. High score + converging → refine
    if current_score >= 60 and diversity < 0.3:
        logger.info(f"[meta_evolution] strategy=EXPLOIT (score={current_score}, diversity={diversity})")
        return EvolutionStrategy.EXPLOIT

    # 3. Plateaued → recombine from history
    if declines >= 2 and n >= 3:
        logger.info(f"[meta_evolution] strategy=RECOMBINE (declines={declines}, n={n})")
        return EvolutionStrategy.RECOMBINE

    # 4. Low score + early → explore new directions
    if current_score < 30 and n <= 3:
        logger.info(f"[meta_evolution] strategy=EXPLORE (score={current_score}, n={n})")
        return EvolutionStrategy.EXPLORE

    # 5. High diversity + not converging → explore
    if diversity > 0.6 and convergence < 0.4:
        logger.info(f"[meta_evolution] strategy=EXPLORE (diversity={diversity}, convergence={convergence})")
        return EvolutionStrategy.EXPLORE

    # 6. Medium score + stable → exploit
    if 30 <= current_score < 60 and stability > 0.6:
        logger.info(f"[meta_evolution] strategy=EXPLOIT (score={current_score}, stability={stability})")
        return EvolutionStrategy.EXPLOIT

    # 7. Score gap between current and best → recombine
    if metrics.best_score - current_score > 20 and n >= 2:
        logger.info(f"[meta_evolution] strategy=RECOMBINE (gap={metrics.best_score - current_score})")
        return EvolutionStrategy.RECOMBINE

    # Default
    logger.info("[meta_evolution] strategy=EXPLOIT (default)")
    return EvolutionStrategy.EXPLOIT
