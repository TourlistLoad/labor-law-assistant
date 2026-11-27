import json

import httpx
import pytest

from labor_law_assistant.gemini import (
    MAX_OUTPUT_TOKENS,
    Answer,
    BlockedError,
    GeminiHTTPError,
    GeminiUnavailable,
    MalformedError,
    Reply,
    TruncatedError,
    ask,
    build_request,
    parse_response,
    retry_reason,
)
from labor_law_assistant.prompts import SYSTEM_INSTRUCTION

KEY = "AIzaSy-test-key-0123456789"
SENT_MODEL = "gemini-3.8-flash"


def ok_body(**answer_fields):
    fields = {
        "answer": "Theo Điều 35 Bộ luật Lao động 2019, ...",
        "in_scope": True,
        "confidence": "high",
    } | answer_fields
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": json.dumps(fields)}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 182,
            "candidatesTokenCount": 140,
            "totalTokenCount": 410,
        },
        "modelVersion": "gemini-3.8-flash-001",
    }


def parse(body):
    return parse_response(httpx.Response(200, json=body), model=SENT_MODEL)


def test_request_key_in_header_not_url():
    request = build_request("Câu hỏi", model=SENT_MODEL, key=KEY)

    assert KEY not in str(request.url)
    assert request.headers["x-goog-api-key"] == KEY
    assert request.url.path == f"/v1beta/models/{SENT_MODEL}:generateContent"


def test_request_body():
    request = build_request("Nghỉ việc báo trước?", model=SENT_MODEL, key=KEY)
    body = json.loads(request.content)

    assert body["systemInstruction"]["parts"][0]["text"] == SYSTEM_INSTRUCTION
    assert body["contents"][0]["parts"][0]["text"] == "Nghỉ việc báo trước?"
    assert body["generationConfig"] == {
        "responseMimeType": "application/json",
        "responseJsonSchema": Answer.model_json_schema(),
        "maxOutputTokens": MAX_OUTPUT_TOKENS,
    }


def test_parse_success_keeps_api_usage_as_is():
    reply = parse(ok_body())

    assert reply.answer == Answer(
        answer="Theo Điều 35 Bộ luật Lao động 2019, ...",
        in_scope=True,
        confidence="high",
    )
    assert reply.model == "gemini-3.8-flash-001"
    # total comes from the API and includes thought tokens: 410, not 182 + 140.
    assert reply.usage.total_tokens == 410
    assert (reply.usage.input_tokens, reply.usage.output_tokens) == (182, 140)


def test_model_falls_back_to_sent_name():
    body = ok_body()
    del body["modelVersion"]

    assert parse(body).model == SENT_MODEL


def test_missing_usage_is_none():
    body = ok_body()
    del body["usageMetadata"]["promptTokenCount"]
    usage = parse(body).usage
    assert (usage.input_tokens, usage.output_tokens) == (None, 140)

    del body["usageMetadata"]
    usage = parse(body).usage
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (
        None,
        None,
        None,
    )


def test_missing_finish_reason_is_success():
    body = ok_body()
    del body["candidates"][0]["finishReason"]

    assert parse(body).answer.in_scope is True


def test_extra_fields_dropped():
    reply = parse(ok_body(source="extra"))

    assert set(reply.answer.model_dump()) == {"answer", "in_scope", "confidence"}


def test_long_answer_kept():
    long_answer = "Người lao động " * 100

    assert parse(ok_body(answer=long_answer)).answer.answer == long_answer


def test_thought_parts_ignored():
    body = ok_body()
    parts = body["candidates"][0]["content"]["parts"]
    parts.insert(0, {"text": "Let me think...", "thought": True})

    assert parse(body).answer.confidence == "high"


def test_prompt_blocked():
    body = ok_body()
    body["promptFeedback"] = {"blockReason": "PROHIBITED_CONTENT"}
    del body["candidates"]

    with pytest.raises(BlockedError) as error:
        parse(body)
    assert error.value.reason == "PROHIBITED_CONTENT"


def test_no_candidates_is_blocked():
    body = ok_body()
    del body["candidates"]

    with pytest.raises(BlockedError) as error:
        parse(body)
    assert error.value.reason is None


@pytest.mark.parametrize(
    "reason", ["SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"]
)
def test_safety_finish_reason_is_blocked(reason):
    body = ok_body()
    body["candidates"][0]["finishReason"] = reason

    with pytest.raises(BlockedError) as error:
        parse(body)
    assert error.value.reason == reason


def test_max_tokens_is_truncated():
    body = ok_body()
    body["candidates"][0]["finishReason"] = "MAX_TOKENS"

    with pytest.raises(TruncatedError):
        parse(body)


@pytest.mark.parametrize(
    "fields",
    [
        {"in_scope": "true"},
        {"confidence": "certain"},
        {"answer": "   "},
    ],
)
def test_wrong_schema_is_malformed(fields):
    with pytest.raises(MalformedError) as error:
        parse(ok_body(**fields))
    assert error.value.finish_reason == "STOP"


def test_invalid_json_text_is_malformed():
    body = ok_body()
    body["candidates"][0]["content"]["parts"] = [{"text": '{"answer": "Theo'}]

    with pytest.raises(MalformedError):
        parse(body)


def test_other_finish_reason_is_malformed():
    body = ok_body()
    body["candidates"][0]["finishReason"] = "OTHER"

    with pytest.raises(MalformedError) as error:
        parse(body)
    assert error.value.finish_reason == "OTHER"


def test_non_json_body_is_malformed():
    response = httpx.Response(200, text="<html>Bad Gateway</html>")

    with pytest.raises(MalformedError) as error:
        parse_response(response, model=SENT_MODEL)
    assert error.value.finish_reason is None


# Bad-key body copied from ai.google.dev/gemini-api/docs/generate-content/api-errors
BAD_KEY_BODY = {
    "error": {
        "code": 400,
        "message": "API key not valid. Please pass a valid API key.",
        "status": "INVALID_ARGUMENT",
        "details": [
            {
                "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                "reason": "API_KEY_INVALID",
                "domain": "googleapis.com",
                "metadata": {"service": "generativelanguage.googleapis.com"},
            },
            {
                "@type": "type.googleapis.com/google.rpc.LocalizedMessage",
                "locale": "en-US",
                "message": "API key not valid. Please pass a valid API key.",
            },
        ],
    }
}


def error_response(status, message="The model is overloaded."):
    return httpx.Response(status, json={"error": {"code": status, "message": message}})


class FakeGemini:
    """Plays back one outcome per call: a response to return or an exception."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.sleeps = []
        self.logs = []

    def send(self, request):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def ask(self):
        return ask(
            "Câu hỏi",
            model=SENT_MODEL,
            key=KEY,
            send=self.send,
            sleep=self.sleeps.append,
            log=self.logs.append,
        )


def test_always_503_gives_up_after_4_attempts():
    fake = FakeGemini(*[error_response(503) for _ in range(4)])

    with pytest.raises(GeminiUnavailable) as error:
        fake.ask()
    assert fake.calls == 4
    assert fake.sleeps == [1, 2, 4]
    assert fake.logs == [
        "Đang thử lại (1/3) sau 1s: HTTP 503",
        "Đang thử lại (2/3) sau 2s: HTTP 503",
        "Đang thử lại (3/3) sau 4s: HTTP 503",
    ]
    assert error.value.last == "HTTP 503: The model is overloaded."


def test_503_then_success():
    fake = FakeGemini(error_response(503), httpx.Response(200, json=ok_body()))

    assert isinstance(fake.ask(), Reply)
    assert fake.calls == 2
    assert fake.sleeps == [1]


def test_400_not_retried():
    fake = FakeGemini(error_response(400, "Invalid JSON payload."))

    with pytest.raises(GeminiHTTPError) as error:
        fake.ask()
    assert fake.calls == 1
    assert (fake.sleeps, fake.logs) == ([], [])
    assert error.value.status == 400
    assert error.value.message == "Invalid JSON payload."
    assert error.value.key_invalid is False


def test_503_then_400_stops_at_400():
    fake = FakeGemini(error_response(503), error_response(400))

    with pytest.raises(GeminiHTTPError) as error:
        fake.ask()
    assert fake.calls == 2
    assert error.value.status == 400


def test_501_not_retried():
    fake = FakeGemini(error_response(501))

    with pytest.raises(GeminiHTTPError) as error:
        fake.ask()
    assert fake.calls == 1
    assert error.value.status == 501


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (httpx.ReadTimeout("timed out"), "hết thời gian chờ 30s"),
        (httpx.ConnectError("connection refused"), "lỗi kết nối"),
    ],
)
def test_transport_errors_retried(exception, reason):
    fake = FakeGemini(exception, httpx.Response(200, json=ok_body()))

    fake.ask()
    assert fake.calls == 2
    assert fake.logs == [f"Đang thử lại (1/3) sau 1s: {reason}"]


def test_transport_error_last_is_reason():
    fake = FakeGemini(*[httpx.ConnectError("refused") for _ in range(4)])

    with pytest.raises(GeminiUnavailable) as error:
        fake.ask()
    assert error.value.last == "lỗi kết nối"


def test_bad_key_body_from_docs_is_key_invalid():
    fake = FakeGemini(httpx.Response(400, json=BAD_KEY_BODY))

    with pytest.raises(GeminiHTTPError) as error:
        fake.ask()
    assert fake.calls == 1
    assert error.value.key_invalid is True
    assert error.value.message == "API key not valid. Please pass a valid API key."


def test_non_json_error_uses_reason_phrase():
    fake = FakeGemini(httpx.Response(404, text="<html>Not here</html>"))

    with pytest.raises(GeminiHTTPError) as error:
        fake.ask()
    assert error.value.message == "Not Found"


@pytest.mark.parametrize(
    ("status", "reason"),
    [(code, f"HTTP {code}") for code in (408, 429, 500, 502, 503, 504)]
    + [(code, None) for code in (400, 401, 403, 404, 501)],
)
def test_retry_classification(status, reason):
    error = GeminiHTTPError(status, "message", key_invalid=False)

    assert retry_reason(error) == reason


def test_parse_errors_not_retried():
    fake = FakeGemini(httpx.Response(200, json=ok_body(in_scope="true")))

    with pytest.raises(MalformedError):
        fake.ask()
    assert fake.calls == 1
    assert (fake.sleeps, fake.logs) == ([], [])
