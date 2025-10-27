from __future__ import annotations

from analysis.models.domain import AnalysisInput, InputArticle
from analysis.prompts.templates import build_analysis_messages


def _ai(max_chars: int = 600):
    items = [
        InputArticle(
            title="A very long title that should be fine",
            body="A" * 1000 + " end",
            url="https://example.com/a1",
            language="en",
        ),
        InputArticle(
            title="Second",
            body="B" * 300,
            url="https://example.com/a2",
            language="en",
        ),
    ]
    return AnalysisInput(ticker="aapl", locale="ko_KR", items=items, max_chars=max_chars)


def test_build_messages_contains_system_and_user_and_schema():
    ai = _ai(500)
    msgs = build_analysis_messages(ai, tone="neutral")
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "JSON" in msgs[0]["content"]
    assert "Ticker" in msgs[1]["content"]
    assert "[Articles]" in msgs[1]["content"]


def test_trimming_respects_max_chars():
    # With 500 chars, only part of first (1000) should appear, second likely excluded
    ai = _ai(500)
    msgs = build_analysis_messages(ai)
    user = msgs[1]["content"]
    # Ensure second article likely missing due to budget
    assert user.count("Title:") == 1
    # Body length should be trimmed well below original 1000
    assert "A" * 600 not in user
