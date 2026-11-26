"""Gemini adapter: the only module that knows httpx and the REST format."""

from dataclasses import dataclass
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from labor_law_assistant.prompts import SYSTEM_INSTRUCTION

DEFAULT_MODEL = "gemini-3.8-flash"
# Thought tokens count toward this limit, so it leaves room for thinking.
MAX_OUTPUT_TOKENS = 8192
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
SAFETY_REASONS = frozenset(
    {"SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"}
)


class Answer(BaseModel):
    # strict: lax mode would turn "true" into True instead of rejecting it.
    model_config = ConfigDict(strict=True, extra="ignore")

    answer: str
    in_scope: bool
    confidence: Literal["high", "medium", "low"]

    @field_validator("answer")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("answer is blank")
        return value


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class Reply:
    answer: Answer
    model: str
    usage: Usage


class BlockedError(Exception):
    def __init__(self, reason: str | None) -> None:
        super().__init__(reason)
        self.reason = reason


class TruncatedError(Exception):
    pass


class MalformedError(Exception):
    def __init__(self, finish_reason: str | None) -> None:
        super().__init__(finish_reason)
        self.finish_reason = finish_reason


def build_request(question: str, *, model: str, key: str) -> httpx.Request:
    return httpx.Request(
        "POST",
        API_URL.format(model=model),
        headers={"x-goog-api-key": key},
        json={
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": question}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": Answer.model_json_schema(),
                "maxOutputTokens": MAX_OUTPUT_TOKENS,
            },
        },
    )


def parse_response(response: httpx.Response, *, model: str) -> Reply:
    try:
        body: dict[str, Any] = response.json()
    except ValueError:
        raise MalformedError(None) from None

    block_reason = body.get("promptFeedback", {}).get("blockReason")
    if block_reason:
        raise BlockedError(block_reason)
    candidates = body.get("candidates")
    if not candidates:
        raise BlockedError(None)

    candidate = candidates[0]
    finish_reason = candidate.get("finishReason")
    if finish_reason in SAFETY_REASONS:
        raise BlockedError(finish_reason)
    if finish_reason == "MAX_TOKENS":
        raise TruncatedError()
    if finish_reason not in (None, "STOP"):
        raise MalformedError(finish_reason)

    parts = candidate.get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    try:
        answer = Answer.model_validate_json(text)
    except ValidationError:
        raise MalformedError(finish_reason) from None

    usage = body.get("usageMetadata", {})
    return Reply(
        answer=answer,
        model=body.get("modelVersion") or model,
        usage=Usage(
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
            total_tokens=usage.get("totalTokenCount"),
        ),
    )
