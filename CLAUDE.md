# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Cách làm việc trong repo này
- Người dùng đang học. Giải thích quyết định thiết kế, không chỉ đưa code.
- Việc đụng từ 2 file trở lên: lập kế hoạch và chờ duyệt trước khi sửa.
- Mỗi thay đổi đi theo 1 spec trong docs/specs/. Không làm ngoài phạm vi spec;
  thấy việc đáng làm thêm thì ghi vào mục "Đề xuất" cuối spec, không tự làm.
- Pull request nhỏ: dưới 300 dòng diff, 1 mục đích.
- Mọi thay đổi logic phải có test. Chạy `uv run pytest -q` trước khi báo xong
  và dán kết quả thật.
- Không viết hộ file spec. Không viết hộ mục "Teach-back" trong pull request.
  Được phản biện hai thứ này khi được hỏi.
- Không đọc, in ra hay commit `.env`. Không thêm dependency mới khi chưa hỏi.


## Commands

All tooling runs through `uv` (Python 3.14, pinned in `.python-version`).

```bash
uv sync                                   # create .venv and install project (editable) + dev group
uv run pytest                             # run all tests (testpaths = tests)
uv run pytest tests/test_health.py::test_health_returns_ok   # run a single test
uv run ruff check .                       # lint (rules: E, F, I, UP, B; line length 88)
uv run ruff format .                      # format
uv add <pkg>                              # add a runtime dependency (updates pyproject.toml and uv.lock)
uv add --dev <pkg>                        # add to the dev dependency group
```

Never edit `uv.lock` by hand; commit it together with `pyproject.toml`.

## Project state

Early skeleton. The package `labor_law_assistant` currently exposes only `health() -> "ok"`, covered by `tests/test_health.py`. There are no runtime dependencies yet: no LLM client, vector store, or ingestion code exists. `.env.example` declares `GEMINI_API_KEY`, which indicates Gemini is the intended LLM provider, but nothing reads it yet. Do not assume a framework or storage backend; check `pyproject.toml` first.

## Layout and packaging

- src layout: code lives in `src/labor_law_assistant/`. The build backend is `uv_build`, which looks for the module under `src/` by default. Moving the package out of `src/` requires setting `[tool.uv.build-backend] module-root`.
- The project is installed in editable mode via a `.pth` file pointing at `src/`. Tests import the installed package, not the source tree, so run them with `uv run` rather than a bare `python`.
- `py.typed` is present: the package ships type hints (PEP 561). Keep public functions annotated.
- `tests/` has no `__init__.py` (pytest default `prepend` import mode).

## Repository notes

- This directory is its own git repository, nested inside the outer `workspace_vibecoding` repo. Run git commands from here.
- `.env` holds secrets and is gitignored; only `.env.example` is committed. Add new environment variables to `.env.example` with an empty value.
- `docs/LEARNING_LOG.md` is the owner's personal study notes (in Vietnamese), not a spec or design document. Do not edit it unless asked.
