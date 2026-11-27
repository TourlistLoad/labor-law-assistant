"""Command line entry point: `lla ask <question...>`."""

import argparse
import functools
import json
import os
import sys
import time
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict

import httpx

from labor_law_assistant.gemini import (
    DEFAULT_MODEL,
    RETRY_DELAYS,
    TIMEOUT_SECONDS,
    BlockedError,
    GeminiHTTPError,
    GeminiUnavailable,
    MalformedError,
    Reply,
    TruncatedError,
)
from labor_law_assistant.gemini import ask as gemini_ask

MAX_QUESTION_LENGTH = 2000
# Longest piece of exception text that goes into an error message.
MAX_DETAIL_LENGTH = 300
KEY_HINT = "Kiểm tra GEMINI_API_KEY."
HINTS = {
    400: KEY_HINT,
    401: KEY_HINT,
    403: "Kiểm tra GEMINI_API_KEY, và API đã được bật"
    " hay khu vực có được hỗ trợ không.",
    404: "Kiểm tra GEMINI_MODEL.",
}


class InputError(Exception):
    """Bad input or configuration that the user can fix."""


def _mask(text: str, key: str) -> str:
    # An empty key would match between every character.
    return text.replace(key, "***") if key else text


def _snip(text: str, key: str) -> str:
    # Mask first: clipping first could cut the key in half and leak its front part.
    return _mask(text, key)[:MAX_DETAIL_LENGTH]


def _in_parens(value: str | None) -> str:
    return f" ({value})" if value else ""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lla")
    commands = parser.add_subparsers(dest="command", required=True)
    ask = commands.add_parser("ask", help="hỏi một câu về luật lao động Việt Nam")
    ask.add_argument("question", nargs="+", help="câu hỏi, có thể gồm nhiều từ")
    return parser


def _describe(error: Exception, key: str) -> tuple[str, int]:
    """Turn an exception into the stderr message and exit code from the spec."""
    match error:
        case InputError():
            return f"Lỗi: {error}", 2
        case GeminiHTTPError():
            detail = f"(HTTP {error.status}): {_snip(error.message, key)}"
            if error.status == 400 and not error.key_invalid:
                hint = None
            else:
                hint = HINTS.get(error.status)
            if hint:
                return f"Lỗi từ Gemini {detail} {hint}", 2
            if error.status >= 500:
                return f"Lỗi từ Gemini {detail}", 3
            return f"Lỗi chương trình: Gemini từ chối request {detail}", 1
        case GeminiUnavailable():
            attempts = len(RETRY_DELAYS) + 1
            last = _snip(error.last, key)
            return f"Lỗi: Gemini không phản hồi sau {attempts} lần thử ({last})", 3
        case BlockedError():
            return "Lỗi: phản hồi bị chặn" + _in_parens(error.reason), 4
        case TruncatedError():
            return "Lỗi: phản hồi bị cắt vì hết giới hạn token", 4
        case MalformedError():
            message = "Lỗi: phản hồi của model không đúng định dạng"
            return message + _in_parens(error.finish_reason), 4
        case _:
            detail = _snip(str(error), key)
            return f"Lỗi không mong đợi: {type(error).__name__}: {detail}", 1


def _ask(
    words: Sequence[str],
    *,
    key: str,
    env: Mapping[str, str],
    ask: Callable[..., Reply],
    err: Callable[[str], None],
) -> int:
    if not key:
        raise InputError(
            "chưa có GEMINI_API_KEY. Copy .env.example thành .env rồi điền key."
        )
    question = unicodedata.normalize("NFC", " ".join(words)).strip()
    if not question:
        raise InputError("câu hỏi rỗng.")
    if len(question) > MAX_QUESTION_LENGTH:
        raise InputError(
            f"câu hỏi dài {len(question)} ký tự, tối đa {MAX_QUESTION_LENGTH}."
        )
    model = env.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL

    reply = ask(question, model=model, key=key, log=err)

    usage = asdict(reply.usage)
    output = reply.answer.model_dump() | {"model": reply.model, "usage": usage}
    print(_mask(json.dumps(output, ensure_ascii=False), key))
    missing = [name for name, value in usage.items() if value is None]
    if missing:
        err(f"Cảnh báo: API không trả số token: {', '.join(missing)}")
    return 0


def main(
    argv: Sequence[str], *, env: Mapping[str, str], ask: Callable[..., Reply]
) -> int:
    """Run the CLI; `ask` has the signature of gemini.ask without send and sleep."""
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exit_:
        # argparse has already printed usage to stderr: 2 for bad syntax, 0 for -h.
        return int(exit_.code or 0)

    key = env.get("GEMINI_API_KEY", "").strip()

    def err(line: str) -> None:
        # Every stderr line goes through here, retry log included.
        print(_mask(line, key), file=sys.stderr)

    try:
        return _ask(args.question, key=key, env=env, ask=ask, err=err)
    except KeyboardInterrupt:
        err("Đã hủy")
        return 130
    except Exception as error:
        message, code = _describe(error, key)
        err(message)
        return code


def run() -> None:
    """Console script `lla`: the only place that builds a real HTTP client."""
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        ask = functools.partial(gemini_ask, send=client.send, sleep=time.sleep)
        code = main(sys.argv[1:], env=os.environ, ask=ask)
    sys.exit(code)
