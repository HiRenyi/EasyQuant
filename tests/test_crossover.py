"""Tests for crossover_engine.py."""

from quantgpt.crossover_engine import build_crossover_prompt, extract_top_segments


class TestExtractTopSegments:
    def test_empty_input(self):
        assert extract_top_segments([]) == []

    def test_filters_by_score_ratio(self):
        iters = [
            {"expression": "a", "score": 100},
            {"expression": "b", "score": 60},
            {"expression": "c", "score": 30},
        ]
        result = extract_top_segments(iters, min_score_ratio=0.5)
        assert len(result) == 2
        assert result[0]["expression"] == "a"
        assert result[1]["expression"] == "b"

    def test_returns_max_five(self):
        iters = [{"expression": f"e{i}", "score": 80 + i} for i in range(10)]
        result = extract_top_segments(iters)
        assert len(result) <= 5

    def test_sorted_by_score_descending(self):
        iters = [
            {"expression": "low", "score": 40},
            {"expression": "high", "score": 90},
            {"expression": "mid", "score": 70},
        ]
        result = extract_top_segments(iters)
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_excludes_missing_expression(self):
        iters = [
            {"expression": "a", "score": 80},
            {"score": 70},
            {"expression": "", "score": 60},
        ]
        result = extract_top_segments(iters)
        assert len(result) == 1


class TestBuildCrossoverPrompt:
    def test_returns_two_strings(self):
        segments = [{"expression": "rank(close)", "score": 80}]
        sys_p, user_p = build_crossover_prompt(segments, "ts_mean(close,5)", 50)
        assert isinstance(sys_p, str)
        assert isinstance(user_p, str)

    def test_system_prompt_contains_strategy(self):
        segments = [{"expression": "rank(close)", "score": 80}]
        sys_p, _ = build_crossover_prompt(segments, "x", 50)
        assert "重组策略" in sys_p

    def test_user_prompt_contains_segments(self):
        segments = [
            {"expression": "rank(close)", "score": 80},
            {"expression": "zscore(volume)", "score": 70},
        ]
        _, user_p = build_crossover_prompt(segments, "current_expr", 50)
        assert "rank(close)" in user_p
        assert "zscore(volume)" in user_p
        assert "current_expr" in user_p

    def test_operators_doc_included(self):
        segments = [{"expression": "x", "score": 50}]
        sys_p, _ = build_crossover_prompt(segments, "y", 40, operators_doc="## Custom Ops\nfoo()")
        assert "Custom Ops" in sys_p
