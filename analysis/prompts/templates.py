"""프롬프트 템플릿/빌더.

LLM에게 구조화(JSON) 출력을 요청하는 시스템/유저 메시지를 생성한다.
입력 기사 길이는 max_chars를 초과하지 않도록 잘라낸다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from analysis.models.domain import AnalysisInput, InputArticle


JSON_SCHEMA_SNIPPET = (
    "{"
    '"summary_text": string (<=1200 chars, newline allowed), '
    '"keywords": array<string> (3-10 unique, lowercase, no punctuation), '
    '"sentiment_score": number (-1.0..1.0), '
    '"anomalies": array<object> where object = {"label": string (<=64), "description": string (<=512), "score": number (0.0..1.0)}'
    "}"
)


def _trim_articles(items: List[InputArticle], max_chars: int) -> List[Tuple[str, str]]:
    """Return list of (title, body_excerpt) trimmed to fit total <= max_chars.

    Simple greedy concatenation: stop when limit reached.
    """
    result: List[Tuple[str, str]] = []
    used = 0
    for it in items:
        title = it.title.strip()
        body = it.body.strip()
        # Leave room for formatting tokens between entries
        header = f"Title: {title}\n"
        budget = max_chars - used - len(header)
        if budget <= 0:
            break
        excerpt = body[: budget]
        used += len(header) + len(excerpt) + 2  # 2 for newline spacing
        result.append((title, excerpt))
        if used >= max_chars:
            break
    return result


def build_analysis_messages(inp: AnalysisInput, *, tone: str = "neutral") -> List[dict]:
    """Build chat messages instructing the model to produce structured JSON.

    - System: role, locale, tone, safety rules, JSON schema
    - User: ticker and trimmed articles
    """
    locale = inp.locale
    system = (
        "역할: 당신은 금융 도메인에 특화된 리서치 애널리스트 보조입니다.\n"
        "목표: 제공된 기사들을 기반으로 특정 종목의 하루치 주요 동향을\n"
        "- 사실 기반 요약(summary)\n"
        "- 핵심 키워드(keywords)\n"
        "- 종합 감성 점수(sentiment_score)\n"
        "- 이상 이벤트 목록(anomalies)\n"
        "로 구조화하여 산출합니다.\n\n"
        "출력 형식: JSON ONLY (추가 설명/코드블록/머리말 금지). 스키마: "
        f"{JSON_SCHEMA_SNIPPET}.\n\n"
        "규칙:\n"
        "1) 사실만 기술하고, 출처 기사에 없는 수치/사실은 생성하지 않습니다.\n"
        "2) 불확실하거나 정보가 부족하면 해당 항목을 비워두지 말고\n"
        "   사실 부족을 명시적으로 설명합니다(예: anomalies는 빈 배열).\n"
        "3) summary_text는 투자 자문 문구를 피하고, 과도한 확신/미확인 루머 금지.\n"
        "4) keywords: 3~10개, 소문자, 공백 기준 토큰, 중복/불용부호 제거.\n"
        "5) sentiment_score: -1.0(매우 부정) ~ 1.0(매우 긍정), 0은 중립.\n"
        "6) anomalies: 비정상 패턴(깜짝 실적, 대규모 인수, 규제/소송, 경영 교체,\n"
        "   급등락 신호 등)을 간결히 기술하고, score는 신뢰/강도(0~1).\n"
        "7) 언어/톤: locale과 tone을 따릅니다.\n"
        f"8) locale={locale}, tone={tone}.\n"
    )

    trimmed = _trim_articles(inp.items, inp.max_chars)
    lines: List[str] = [
        f"[Ticker] {inp.ticker}",
        f"[Locale] {locale}",
        "[Instructions] 기사 목록을 읽고 위 규칙에 따라 JSON만 출력하세요.",
        "[Articles]",
    ]
    for idx, (title, body) in enumerate(trimmed, start=1):
        lines.append(f"{idx}. Title: {title}")
        lines.append("Body: ")
        lines.append(body)
        lines.append("")
    user = "\n".join(lines)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
