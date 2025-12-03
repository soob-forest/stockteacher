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
import math
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
StreamProviderFn = Callable[[Dict[str, Any]], Iterator[Any]]


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


def _estimate_tokens_from_messages(messages: List[dict]) -> int:
    """길이 기반 보수적 토큰 추정."""
    total_chars = 0
    for message in messages:
        content = message.get("content", "") if isinstance(message, dict) else ""
        total_chars += len(str(content))
    return max(1, math.ceil(total_chars / 4))


def _load_structured_content(content: str, attempts_left: int) -> Dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        if attempts_left > 0:
            raise TransientLLMError("LLM 응답 JSON 파싱 실패") from exc
        raise PermanentLLMError("LLM 응답 JSON 파싱 실패") from exc


@dataclass(frozen=True)
class OpenAIClient:
    settings: AnalysisSettings
    provider: Optional[ProviderFn] = None
    stream_provider: Optional[StreamProviderFn] = None

    @classmethod
    def from_env(
        cls,
        provider: Optional[ProviderFn] = None,
        stream_provider: Optional[StreamProviderFn] = None,
    ) -> "OpenAIClient":
        return cls(get_analysis_settings(), provider=provider, stream_provider=stream_provider)

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
                data = _load_structured_content(
                    content, int(self.settings.analysis_retry_max_attempts) - attempts
                )
                return AnalysisResult(
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
        *,
        max_cost_usd: Optional[float] = None,
        request_timeout_seconds: Optional[float] = None,
        stream_provider: Optional[StreamProviderFn] = None,
        retry_max_attempts: Optional[int] = None,
    ) -> Iterator[str]:
        """OpenAI Chat Completion API를 스트리밍 모드로 호출."""
        payload, timeout = self._prepare_stream_payload(
            messages=messages, model=model, max_tokens=max_tokens, temperature=temperature,
            max_cost_usd=max_cost_usd, request_timeout_seconds=request_timeout_seconds,
        )
        provider = stream_provider or self.stream_provider
        max_attempts = int(retry_max_attempts) if retry_max_attempts is not None else int(
            self.settings.analysis_retry_max_attempts
        )
        attempts = 0
        last_exc: Optional[Exception] = None

        while attempts <= max_attempts:
            attempts += 1
            try:
                yield from self._stream_with_provider(
                    provider=provider,
                    payload=payload,
                    timeout=timeout,
                    started_at=time.monotonic(),
                )
                return
            except PermanentLLMError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempts > max_attempts:
                    break

        assert last_exc is not None
        if isinstance(last_exc, TransientLLMError):
            raise last_exc
        raise TransientLLMError(f"스트리밍 실패: {last_exc}") from last_exc

    def _prepare_stream_payload(
        self,
        *,
        messages: List[dict],
        model: Optional[str],
        max_tokens: Optional[int],
        temperature: Optional[float],
        max_cost_usd: Optional[float],
        request_timeout_seconds: Optional[float],
    ) -> tuple[Dict[str, Any], float]:
        model_name = model or self.settings.analysis_model
        completion_tokens = max_tokens or self.settings.analysis_max_tokens
        temp = temperature or self.settings.analysis_temperature
        max_cost = float(max_cost_usd or self.settings.analysis_cost_limit_usd)
        timeout = float(request_timeout_seconds or self.settings.analysis_request_timeout_seconds)

        prompt_tokens = _estimate_tokens_from_messages(messages)
        estimated_cost = _estimate_cost_usd(model_name, prompt_tokens, completion_tokens)
        if estimated_cost > max_cost:
            raise PermanentLLMError("예상 비용 상한 초과")

        return (
            {
                "model": model_name,
                "messages": messages,
                "max_tokens": completion_tokens,
                "temperature": temp,
                "stream": True,
            },
            timeout,
        )

    def _stream_with_provider(
        self,
        *,
        provider: Optional[StreamProviderFn],
        payload: Dict[str, Any],
        timeout: float,
        started_at: float,
    ) -> Iterator[str]:
        stream_provider = provider or self._get_stream_provider()
        try:
            stream = stream_provider(payload)
        except PermanentLLMError:
            raise
        except Exception as exc:
            raise TransientLLMError(f"스트리밍 provider 생성 실패: {exc}") from exc

        for raw_chunk in stream:
            elapsed = time.monotonic() - started_at
            if elapsed > timeout:
                raise TransientLLMError("LLM 요청 타임아웃 초과")

            content = _extract_delta_content(raw_chunk)
            if content:
                yield content

    def _get_stream_provider(self) -> StreamProviderFn:
        if self.stream_provider is not None:
            return self.stream_provider

        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:
            raise PermanentLLMError("openai 라이브러리를 찾을 수 없습니다.") from exc

        client = OpenAI(api_key=self.settings.openai_api_key)

        def _call(payload: Dict[str, Any]) -> Iterator[Any]:  # pragma: no cover - 네트워크 미사용
            return client.chat.completions.create(**payload)

        return _call


def _extract_delta_content(chunk: Any) -> str:
    """OpenAI/테스트 chunk 객체에서 delta.content를 추출."""
    if isinstance(chunk, dict):
        choices = chunk.get("choices") or []
        if choices:
            delta = choices[0].get("delta") or choices[0].get("message") or {}
            content = delta.get("content") if isinstance(delta, dict) else None
            return content or ""

    choices = getattr(chunk, "choices", None)
    if choices:
        choice = choices[0] if len(choices) > 0 else None
        if choice:
            delta = getattr(choice, "delta", None)
            if delta and getattr(delta, "content", None):
                return delta.content
            message = getattr(choice, "message", None)
            if message and getattr(message, "content", None):
                return message.content
    return ""
