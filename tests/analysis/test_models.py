from __future__ import annotations

import pytest

from analysis.models.domain import (
    AnalysisInput,
    AnalysisResult,
    AnomalyItem,
    InputArticle,
)


def _article():
    return InputArticle(
        title="Apple hits new high",
        body="Earnings beat expectations.",
        url="https://example.com/aapl",
        language="en",
    )


def test_analysis_input_validation():
    item = _article()
    ai = AnalysisInput(ticker="aapl", locale="ko_KR", items=[item], max_chars=5000)
    assert ai.ticker == "AAPL"
    assert len(ai.items) == 1

    with pytest.raises(Exception):
        AnalysisInput(ticker=" ", locale="ko_KR", items=[item])

    with pytest.raises(Exception):
        AnalysisInput(ticker="AAPL", locale="ko_KR", items=[])


def test_analysis_result_constraints():
    res = AnalysisResult(
        ticker="aapl",
        summary_text="Strong results and positive outlook",
        keywords=["Apple", "Earnings", "Apple", "  growth  "],
        sentiment_score=0.7,
        anomalies=[AnomalyItem(label="surge", description="Unusual price move", score=0.8)],
        llm_model="gpt-4o-mini",
        llm_tokens_prompt=123,
        llm_tokens_completion=456,
        llm_cost=0.0012,
    )
    assert res.ticker == "AAPL"
    assert res.keywords[:3] == ["Apple", "Earnings", "growth"]
    assert len(res.keywords) == 3

    with pytest.raises(Exception):
        AnalysisResult(
            ticker="AAPL",
            summary_text=" ",
            keywords=[],
            sentiment_score=2.0,
            anomalies=[],
            llm_model="gpt-4o-mini",
            llm_tokens_prompt=0,
            llm_tokens_completion=0,
            llm_cost=0.0,
        )

