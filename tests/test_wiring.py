import functools
import json

import httpx

from labor_law_assistant.cli import main
from labor_law_assistant.gemini import ask

KEY = "AIzaSy-test-key-0123456789"
ANSWER = {"answer": "Theo Điều 35 ...", "in_scope": True, "confidence": "high"}
BODY = {
    "candidates": [
        {"content": {"parts": [{"text": json.dumps(ANSWER)}]}, "finishReason": "STOP"}
    ],
    "usageMetadata": {
        "promptTokenCount": 182,
        "candidatesTokenCount": 140,
        "totalTokenCount": 410,
    },
    "modelVersion": "gemini-3.8-flash-001",
}


def test_main_through_gemini_ask(capsys):
    """main and the real gemini.ask agree on arguments; only the network is fake."""
    sent = []

    def send(request):
        sent.append(request)
        return httpx.Response(200, json=BODY)

    real_ask = functools.partial(ask, send=send, sleep=lambda seconds: None)
    code = main(["ask", "Nghỉ việc?"], env={"GEMINI_API_KEY": KEY}, ask=real_ask)
    out, err = capsys.readouterr()

    assert (code, err) == (0, "")
    assert json.loads(out) == ANSWER | {
        "model": "gemini-3.8-flash-001",
        "usage": {"input_tokens": 182, "output_tokens": 140, "total_tokens": 410},
    }
    assert len(sent) == 1
