import json
import unicodedata
from dataclasses import asdict

import pytest

from labor_law_assistant.cli import main
from labor_law_assistant.gemini import (
    DEFAULT_MODEL,
    Answer,
    BlockedError,
    GeminiHTTPError,
    GeminiUnavailable,
    MalformedError,
    Reply,
    TruncatedError,
    Usage,
)

KEY = "AIzaSy-test-key-0123456789"
ENV = {"GEMINI_API_KEY": KEY}
QUESTION = "Nghỉ việc phải báo trước bao nhiêu ngày?"
ANSWER = "Theo Điều 35 Bộ luật Lao động 2019, ..."
FULL_USAGE = Usage(input_tokens=182, output_tokens=140, total_tokens=410)


def make_reply(answer=ANSWER, in_scope=True, usage=FULL_USAGE):
    return Reply(
        answer=Answer(answer=answer, in_scope=in_scope, confidence="high"),
        model="gemini-3.8-flash-001",
        usage=usage,
    )


class FakeAsk:
    """Stands in for gemini.ask: records the call, writes logs, returns or raises."""

    def __init__(self, outcome=None, logs=()):
        self.outcome = make_reply() if outcome is None else outcome
        self.logs = logs
        self.calls = []

    def __call__(self, question, *, model, key, log):
        self.calls.append({"question": question, "model": model, "key": key})
        for line in self.logs:
            log(line)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def run_cli(capsys, *words, env=ENV, ask=None):
    code = main(["ask", *words], env=env, ask=FakeAsk() if ask is None else ask)
    out, err = capsys.readouterr()
    return code, out, err


def test_success_prints_one_json_line(capsys):
    ask = FakeAsk()
    code, out, err = run_cli(capsys, QUESTION, ask=ask)

    assert (code, err) == (0, "")
    assert out.endswith("\n") and out.count("\n") == 1
    assert "Điều" in out  # Vietnamese is not escaped
    data = json.loads(out)
    assert data == {
        "answer": ANSWER,
        "in_scope": True,
        "confidence": "high",
        "model": "gemini-3.8-flash-001",
        "usage": {"input_tokens": 182, "output_tokens": 140, "total_tokens": 410},
    }
    assert data["in_scope"] is True
    assert ask.calls == [{"question": QUESTION, "model": DEFAULT_MODEL, "key": KEY}]


def test_out_of_scope_exit_0(capsys):
    refusal = "Mình chỉ hỗ trợ câu hỏi về luật lao động Việt Nam."
    ask = FakeAsk(make_reply(answer=refusal, in_scope=False))
    code, out, _ = run_cli(capsys, "Cách nấu phở bò", ask=ask)

    assert code == 0
    assert json.loads(out)["in_scope"] is False


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"GEMINI_API_KEY": ""},
        {"GEMINI_API_KEY": " \t "},
        {"GOOGLE_API_KEY": KEY},
    ],
)
def test_missing_key(capsys, env):
    ask = FakeAsk()

    assert run_cli(capsys, QUESTION, env=env, ask=ask) == (
        2,
        "",
        "Lỗi: chưa có GEMINI_API_KEY. Copy .env.example thành .env rồi điền key.\n",
    )
    assert ask.calls == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, DEFAULT_MODEL), ("", DEFAULT_MODEL), ("  ", DEFAULT_MODEL)]
    + [("gemini-other", "gemini-other")],
)
def test_model_from_env(capsys, value, expected):
    env = ENV if value is None else ENV | {"GEMINI_MODEL": value}
    ask = FakeAsk()
    run_cli(capsys, QUESTION, env=env, ask=ask)

    assert ask.calls[0]["model"] == expected


def test_words_joined(capsys):
    ask = FakeAsk()
    run_cli(capsys, "  Nghỉ", "việc", "báo trước?  ", ask=ask)

    assert ask.calls[0]["question"] == "Nghỉ việc báo trước?"


def test_blank_question(capsys):
    ask = FakeAsk()

    assert run_cli(capsys, "   ", ask=ask) == (2, "", "Lỗi: câu hỏi rỗng.\n")
    assert ask.calls == []


def test_nfd_accepted_after_nfc(capsys):
    # "ế" is 3 code points in NFD and 1 in NFC.
    question = unicodedata.normalize("NFD", "ế" * 2000)
    assert len(question) > 2000
    ask = FakeAsk()

    assert run_cli(capsys, question, ask=ask)[0] == 0
    assert ask.calls[0]["question"] == "ế" * 2000


def test_too_long_reports_nfc_length(capsys):
    question = unicodedata.normalize("NFD", "ế" * 2001)
    ask = FakeAsk()

    assert run_cli(capsys, question, ask=ask) == (
        2,
        "",
        "Lỗi: câu hỏi dài 2001 ký tự, tối đa 2000.\n",
    )
    assert ask.calls == []


@pytest.mark.parametrize("argv", [[], ["ask"], ["hoi", "Lương tối thiểu?"]])
def test_bad_syntax(capsys, argv):
    ask = FakeAsk()
    code = main(argv, env=ENV, ask=ask)

    assert (code, capsys.readouterr().out) == (2, "")
    assert ask.calls == []


KEY_HINT = "Kiểm tra GEMINI_API_KEY."
REGION_HINT = (
    "Kiểm tra GEMINI_API_KEY, và API đã được bật hay khu vực có được hỗ trợ không."
)


@pytest.mark.parametrize(
    ("status", "key_invalid", "code", "expected"),
    [
        (401, False, 2, f"Lỗi từ Gemini (HTTP 401): Sai. {KEY_HINT}"),
        (403, False, 2, f"Lỗi từ Gemini (HTTP 403): Sai. {REGION_HINT}"),
        (404, False, 2, "Lỗi từ Gemini (HTTP 404): Sai. Kiểm tra GEMINI_MODEL."),
        (400, True, 2, f"Lỗi từ Gemini (HTTP 400): Sai. {KEY_HINT}"),
        (400, False, 1, "Lỗi chương trình: Gemini từ chối request (HTTP 400): Sai."),
        (409, False, 1, "Lỗi chương trình: Gemini từ chối request (HTTP 409): Sai."),
        (501, False, 3, "Lỗi từ Gemini (HTTP 501): Sai."),
    ],
)
def test_http_error_mapping(capsys, status, key_invalid, code, expected):
    ask = FakeAsk(GeminiHTTPError(status, "Sai.", key_invalid=key_invalid))

    assert run_cli(capsys, QUESTION, ask=ask) == (code, "", expected + "\n")


def test_unavailable_exit_3(capsys):
    ask = FakeAsk(GeminiUnavailable("HTTP 503: The model is overloaded."))

    assert run_cli(capsys, QUESTION, ask=ask) == (
        3,
        "",
        "Lỗi: Gemini không phản hồi sau 4 lần thử"
        " (HTTP 503: The model is overloaded.)\n",
    )


def test_retry_log_goes_to_stderr(capsys):
    logs = (
        "Đang thử lại (1/3) sau 1s: HTTP 503",
        "Đang thử lại (2/3) sau 2s: hết thời gian chờ 30s",
    )
    code, out, err = run_cli(capsys, QUESTION, ask=FakeAsk(logs=logs))

    assert code == 0
    assert err.splitlines() == list(logs)
    assert json.loads(out)["answer"] == ANSWER


@pytest.mark.parametrize(
    ("reason", "expected"),
    [("SAFETY", "Lỗi: phản hồi bị chặn (SAFETY)"), (None, "Lỗi: phản hồi bị chặn")],
)
def test_blocked(capsys, reason, expected):
    ask = FakeAsk(BlockedError(reason))

    assert run_cli(capsys, QUESTION, ask=ask) == (4, "", expected + "\n")


def test_truncated(capsys):
    assert run_cli(capsys, QUESTION, ask=FakeAsk(TruncatedError())) == (
        4,
        "",
        "Lỗi: phản hồi bị cắt vì hết giới hạn token\n",
    )


@pytest.mark.parametrize(
    ("finish_reason", "suffix"),
    [("STOP", " (STOP)"), ("OTHER", " (OTHER)"), (None, "")],
)
def test_malformed(capsys, finish_reason, suffix):
    ask = FakeAsk(MalformedError(finish_reason))

    assert run_cli(capsys, QUESTION, ask=ask) == (
        4,
        "",
        f"Lỗi: phản hồi của model không đúng định dạng{suffix}\n",
    )


@pytest.mark.parametrize(
    ("usage", "missing"),
    [
        (Usage(None, 140, None), "input_tokens, total_tokens"),
        (Usage(None, None, None), "input_tokens, output_tokens, total_tokens"),
    ],
)
def test_missing_usage_warns_once(capsys, usage, missing):
    ask = FakeAsk(make_reply(usage=usage))
    code, out, err = run_cli(capsys, QUESTION, ask=ask)

    assert code == 0
    assert err == f"Cảnh báo: API không trả số token: {missing}\n"
    assert json.loads(out)["usage"] == asdict(usage)


def test_long_answer_not_clipped(capsys):
    long_answer = "Người lao động " * 100
    ask = FakeAsk(make_reply(answer=long_answer))
    _, out, _ = run_cli(capsys, QUESTION, ask=ask)

    assert json.loads(out)["answer"] == long_answer


def test_error_detail_clipped(capsys):
    ask = FakeAsk(GeminiHTTPError(501, "x" * 1000, key_invalid=False))
    _, _, err = run_cli(capsys, QUESTION, ask=ask)

    assert err == "Lỗi từ Gemini (HTTP 501): " + "x" * 300 + "\n"


LEAK = f"bad key {KEY} rejected"


@pytest.mark.parametrize(
    ("outcome", "logs"),
    [
        pytest.param(make_reply(answer=LEAK), (), id="stdout"),
        pytest.param(GeminiHTTPError(400, LEAK, True), (), id="http-message"),
        pytest.param(GeminiUnavailable(f"HTTP 503: {LEAK}"), (), id="last"),
        pytest.param(None, (f"Đang thử lại (1/3) sau 1s: {LEAK}",), id="retry-log"),
        pytest.param(RuntimeError(LEAK), (), id="unexpected"),
    ],
)
def test_key_masked_everywhere(capsys, outcome, logs):
    _, out, err = run_cli(capsys, QUESTION, ask=FakeAsk(outcome, logs))

    assert KEY not in out + err
    assert "bad key *** rejected" in out + err


def test_key_straddling_300_masked(capsys):
    # Clipping before masking would print the key's first 5 characters.
    ask = FakeAsk(GeminiHTTPError(501, "x" * 295 + KEY, key_invalid=False))
    _, _, err = run_cli(capsys, QUESTION, ask=ask)

    assert KEY[:5] not in err
    assert err == "Lỗi từ Gemini (HTTP 501): " + "x" * 295 + "***\n"


def test_unexpected_exception(capsys):
    ask = FakeAsk(RuntimeError("boom"))

    assert run_cli(capsys, QUESTION, ask=ask) == (
        1,
        "",
        "Lỗi không mong đợi: RuntimeError: boom\n",
    )


def test_keyboard_interrupt(capsys):
    ask = FakeAsk(KeyboardInterrupt())

    assert run_cli(capsys, QUESTION, ask=ask) == (130, "", "Đã hủy\n")
