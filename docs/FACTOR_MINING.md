# Factor Mining Methodology

AI-driven autonomous factor research loop: read notes → design factors → backtest → analyze → update knowledge base → iterate.

---

## Overview

QuantGPT includes a systematic factor mining framework that combines LLM-based factor design with rigorous statistical validation. The process is structured into 6 phases, with built-in research discipline and cross-review mechanisms.

The core tooling lives in [`scripts/factor_miner.py`](../scripts/factor_miner.py) — a stateless utility library for batch-submitting factor expressions to the QuantGPT server and parsing results.

---

## Research Loop (6 Phases)

### Phase 0: Environment Check & Context Loading

1. Verify the backtest server is healthy
2. Load the target research notebook (e.g., `research_notes/archive/factor-mine-reversal.md`)
3. Review: current baseline (expression + metrics), key findings, completed experiments (avoid repeats), next directions
4. Load the knowledge base (`research_notes/knowledge/INDEX.md`): rules (must follow), findings (reference), failures (do not repeat)
5. Identify starting point: first uncompleted direction

### Phase 1: Factor Design

Design 1–3 factor expressions based on research context and knowledge base:

- **State hypothesis** (one sentence)
- **Use valid operators** — 50+ available (see [Operator Reference](#operator-reference) below)
- **Constraints**: max 300 characters, max 8 nesting levels, no forbidden variable names
- **Design principles**:
  - Ratio > multiplication > addition: `rank(A/(B+eps))` > `rank(A)*rank(B)`
  - Nonlinear compression: `sign_power`, `tanh`, `sigmoid` for extreme values
  - Conditional gating: `where()`, `trade_when()` for regime-dependent behavior
  - Simplicity: >4 nesting levels usually degrades performance

### Phase 2: Batch Backtest Submission

```python
from scripts.factor_miner import batch_evaluate

results = batch_evaluate(
    server="http://localhost:8003",
    expressions=[
        "rank(ts_delta(close, 5) / ts_shift(close, 5))",
        "rank(close / ts_mean(close, 10))",
        # ... 10-20 expressions per batch
    ],
    params={
        "universe": "hs300",
        "holding_period": 5,
        "n_groups": 5,
        "benchmark": "hs300",
        "start_date": "2021-01-01",
        "end_date": "2024-12-31",
    },
    max_concurrent=10,
)
```

- Two-phase concurrency: submit all (with 3-wave retry), then poll all
- Results sorted by fitness descending
- If hs300 fitness < 0.1, skip csi500 validation

### Phase 3: Four-Step Analysis

**Every conclusion must pass all four steps — no exceptions.**

**Step 1 — Fact Collection**: Extract metrics, compare against baseline, no conclusions yet.

| Metric | Baseline | Current | Delta |
|--------|----------|---------|-------|
| Fitness | — | — | — |
| Sharpe | — | — | — |
| Returns | — | — | — |
| Turnover | — | — | — |
| IC | — | — | — |
| Rating | — | — | — |

**Step 2 — Independent Judgment**: Form conclusions based on facts. Was the hypothesis validated? If fitness is low, diagnose: is Sharpe insufficient, returns too low, or turnover too high?

**Step 3 — Cross-Review**: Submit facts + judgment to a second LLM (DeepSeek Reasoner) for independent assessment. This is mandatory for any conclusion that includes actionable words: adopt, reject, recommend, next step, kill direction.

**Step 4 — Consensus**: If both agree → output consensus conclusion. If they disagree → present both positions with evidence, adopt the more conservative conclusion.

### Phase 4: Update Research Notes

1. Append experiment record (expression, parameters, metrics, analysis, conclusion)
2. Update baseline if a new best is found
3. Update key findings if cross-experiment insights emerge
4. Mark completed directions (strikethrough)
5. Update knowledge base for cross-session insights:
   - Stable rules → `knowledge/rules/`
   - Empirical findings → `knowledge/findings/`
   - Disproven paths → `knowledge/failures/`

### Phase 5: Continue or Stop

Stop conditions (any one triggers stop):
1. Round limit reached
2. Time limit reached
3. Convergence: N consecutive rounds with no improvement (default: 5)
4. All directions exhausted + 2 rounds of auto-generated directions explored

### Phase 6: Summary Report

Output all A/B-rated factors, key findings, new knowledge base entries, and suggested future directions.

---

## Research Discipline

1. **Control variables**: change only one dimension per experiment
2. **No repeated experiments**: check notes and knowledge base first
3. **Label uncertainty**: mark analysis conclusions as "hypothesis, data-driven"
4. **Record failures**: failed experiments are equally valuable — document why
5. **Simplicity over complexity**: a clean expression beats 6-layer nesting
6. **Knowledge base is an asset**: every meaningful finding should be persisted

---

## Operator Reference

### WQ BRAIN Compatible Operators

These operators produce expressions that can be directly submitted to WorldQuant BRAIN for independent validation.

| Category | Operators |
|----------|-----------|
| Cross-sectional | `rank(x)`, `zscore(x)`, `scale(x)`, `group_rank(x, group)`, `group_zscore(x, group)` |
| Unary math | `abs(x)`, `sign(x)`, `log(x)`, `sqrt(x)` |
| Power | `power(x, e)`, `sign_power(x, e)` |
| Time-series | `ts_mean`, `ts_std`, `ts_max`, `ts_min`, `ts_sum`, `ts_shift`, `ts_delta`, `ts_rank`, `ts_argmax`, `ts_argmin`, `ts_av_diff`, `ts_corr`, `ts_cov`, `decay_linear`, `product` |
| Conditional | `where(cond, t, f)`, `trade_when(cond, alpha, hold)` |
| Binary | `max(a, b)`, `min(a, b)` |
| Special | `adv20`, `returns`, `vwap`, `cap` |
| Variables | `open`, `high`, `low`, `close`, `volume`, `market_cap` |

### Local-Only Operators

Available for local research but not accepted by BRAIN. Use the WQ substitution when preparing for BRAIN submission.

| Operator | WQ Substitute |
|----------|--------------|
| `tanh(x)` | `sign_power(x, 0.5)` |
| `sigmoid(x)` | `rank(x)` |
| `exp(x)` | `power(2.718, x)` |
| `clip(x, lo, hi)` | `max(lo, min(hi, x))` |
| `ts_zscore(x, N)` | `(x - ts_mean(x,N)) / ts_std(x,N)` |
| `ema/sma/wma` | `decay_linear(x,N)` / `ts_mean(x,N)` |
| `rsi/macd/obv/atr` | Hand-write with base operators |

### Proven Expression Templates

These structures have been validated to produce high-fitness factors:

```
rank(ts_delta(close, 5) / ts_shift(close, 5))
rank(close / ts_mean(close, 10))
rank(ts_corr(rank(close), rank(volume), 10))
rank(decay_linear(ts_delta(close, 5) / ts_shift(close, 5), 10))
where(volume > ts_mean(volume, 20),
      rank(close / vwap),
      rank(ts_delta(close, 5) / ts_shift(close, 5)))
```

---

## Fitness Formula

```
Fitness = Sharpe × sqrt(|Returns| / max(Turnover, 0.125))
```

### WQ BRAIN A-Rating Thresholds (CN D1 Quintile)

| Metric | Threshold |
|--------|-----------|
| Sharpe | ≥ 1.625 |
| \|Returns\| | ≥ 6.3% |
| Fitness | ≥ 1.0 |
| Turnover | 1% – 70% |
| Sub-Universe Sharpe | Both halves ≥ 1.19 |

---

## File Structure

| Path | Purpose |
|------|---------|
| `scripts/factor_miner.py` | Submission/polling/parsing utility library |
| `research_notes/TEMPLATE.md` | Research notebook template |
| `research_notes/knowledge/` | Cross-session knowledge base (rules, findings, failures) |
| `research_notes/archive/*.md` | Per-direction research notebooks |

---

## Batch Evaluation API

```python
from scripts.factor_miner import batch_evaluate, evaluate

# Single factor evaluation
result = evaluate(
    server="http://localhost:8003",
    expression="rank(ts_delta(close, 5) / ts_shift(close, 5))",
    params={"universe": "hs300", "holding_period": 5, "n_groups": 5},
)
# Returns: {"expression": "...", "fitness": 0.xxx, "sharpe": ..., "rating": "B", ...}

# Batch evaluation (10-20 expressions, concurrent)
results = batch_evaluate(
    server="http://localhost:8003",
    expressions=["rank(...)", "rank(...)", ...],
    params={...},
    max_concurrent=10,
)
# Returns: list of factor dicts, sorted by fitness descending
```
