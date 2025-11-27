"""OpenAI LLM 클라이언트 래퍼.

특징
- 구조화(JSON) 출력 강제 및 파싱 → AnalysisResult 스키마로 검증
- 재시도/타임아웃/비용 상한(요청당) 적용
- Provider 주입으로 테스트 시 네트워크/실제 의존성 제거
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional

from analysis.models.domain import AnalysisInput, AnalysisResult
from analysis.prompts.templates import build_analysis_messages
from llm.settings import AnalysisSettings, get_analysis_settings


class LLMError(Exception):
    """LLM 호출 관련 기본 오류."""


class TransientLLMError(LLMError):
    """일시 오류(재시도 대상)."""


class PermanentLLMError(LLMError):
    """영구 오류(재시도 불가)."""


ProviderFn = Callable[[Dict[str, Any]], Dict[str, Any]]


_PRICE_PER_1K_TOKENS_USD: Dict[str, Dict[str, float]] = {
    # 샘플 단가(임의 값; 테스트 용). 실제 운영 시 최신 단가를 설정/설정값으로 분리 권장
    "gpt-4o-mini": {"prompt": 0.0005, "completion": 0.0015},
    "gpt-4.1": {"prompt": 0.0030, "completion": 0.0100},
}


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = _PRICE_PER_1K_TOKENS_USD.get(model, _PRICE_PER_1K_TOKENS_USD["gpt-4o-mini"])
    return (
        (prompt_tokens / 1000.0) * price["prompt"]
        + (completion_tokens / 1000.0) * price["completion"]
    )


@dataclass(frozen=True)
class OpenAIClient:
    settings: AnalysisSettings
    provider: Optional[ProviderFn] = None

    @classmethod
    def from_env(cls, provider: Optional[ProviderFn] = None) -> "OpenAIClient":
        return cls(get_analysis_settings(), provider=provider)

    def _get_provider(self) -> ProviderFn:
        if self.provider is not None:
            return self.provider
        # 지연 import: 라이브러리가 없으면 명확한 에러
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover - 테스트에선 provider 주입
            raise PermanentLLMError("openai 라이브러리를 찾을 수 없습니다.") from exc

        client = OpenAI(api_key=self.settings.openai_api_key)

        def _call(payload: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover - 네트워크 미사용
            resp = client.chat.completions.create(**payload)
            # 통일된 dict 형태로 변환
            return {
                "choices": [
                    {
                        "message": {"content": resp.choices[0].message.content},
                    }
                ],
                "usage": {
                    "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(resp.usage, "completion_tokens", 0),
                },
                "model": resp.model,
            }

        return _call

    def _build_payload(self, inp: AnalysisInput) -> Dict[str, Any]:
        msgs = build_analysis_messages(inp)
        return {
            "model": self.settings.analysis_model,
            "messages": msgs,
            "temperature": float(self.settings.analysis_temperature),
            "max_tokens": int(self.settings.analysis_max_tokens),
            "response_format": {"type": "json_object"},
            # 타임아웃은 provider 구현/transport 레벨에서 사용
        }

    def analyze(self, inp: AnalysisInput) -> AnalysisResult:
        payload = self._build_payload(inp)
        provider = self._get_provider()

        attempts = 0
        last_exc: Optional[Exception] = None
        start = time.monotonic()
        while attempts <= int(self.settings.analysis_retry_max_attempts):
            attempts += 1
            try:
                resp = provider(payload)
                model = resp.get("model") or self.settings.analysis_model
                usage = resp.get("usage") or {}
                prompt_tokens = int(usage.get("prompt_tokens", 0))
                completion_tokens = int(usage.get("completion_tokens", 0))
                cost = _estimate_cost_usd(model, prompt_tokens, completion_tokens)
                if cost > float(self.settings.analysis_cost_limit_usd):
                    raise PermanentLLMError("LLM 비용 상한 초과")

                content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as exc:
                    # 첫 JSON 파싱 실패는 재시도, 이후는 영구 실패
                    if attempts <= int(self.settings.analysis_retry_max_attempts):
                        last_exc = exc
                        continue
                    raise PermanentLLMError("LLM 응답 JSON 파싱 실패") from exc

                result = AnalysisResult(
                    ticker=inp.ticker,
                    summary_text=data.get("summary_text", "").strip(),
                    keywords=list(data.get("keywords", []) or []),
                    sentiment_score=float(data.get("sentiment_score", 0.0)),
                    anomalies=list(data.get("anomalies", []) or []),
                    llm_model=model,
                    llm_tokens_prompt=prompt_tokens,
                    llm_tokens_completion=completion_tokens,
                    llm_cost=cost,
                )
                return result
            except TransientLLMError as exc:
                last_exc = exc
                continue
            finally:
                elapsed = time.monotonic() - start
                if elapsed > float(self.settings.analysis_request_timeout_seconds):
                    # 타임아웃은 재시도 대신 종료
                    raise TransientLLMError("LLM 요청 타임아웃 초과")

        assert last_exc is not None
        raise TransientLLMError(f"LLM 호출 재시도 한도 초과: {last_exc}")

    def stream_chat(
        self,
        messages: List[dict],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Iterator[str]:
        """OpenAI Chat Completion API를 스트리밍 모드로 호출.

        Args:
            messages: 대화 메시지 리스트 (OpenAI format)
            model: 모델명 (기본값: settings.analysis_model)
            max_tokens: 최대 토큰 수 (기본값: settings.analysis_max_tokens)
            temperature: 샘플링 온도 (기본값: settings.analysis_temperature)

        Yields:
            str: 각 청크의 텍스트 (delta.content)
        """
        model = model or self.settings.analysis_model
        max_tokens = max_tokens or self.settings.analysis_max_tokens
        temperature = temperature or self.settings.analysis_temperature

        # 지연 import
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:
            raise PermanentLLMError("openai 라이브러리를 찾을 수 없습니다.") from exc

        client = OpenAI(api_key=self.settings.openai_api_key)

        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )

            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content

        except Exception as exc:
            raise TransientLLMError(f"스트리밍 중 오류 발생: {exc}") from exc

