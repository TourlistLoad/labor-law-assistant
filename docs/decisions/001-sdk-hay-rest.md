# ADR 001: Gọi Gemini qua REST (`httpx`) thay vì SDK `google-genai`

- Trạng thái: Đã chấp nhận
- Ngày: 2026-11-26
- Liên quan: [spec 001](../specs/001-hoi-llm-lan-dau.md), Câu hỏi mở 1

## Bối cảnh

Spec 001 là lần đầu project gọi LLM. Spec yêu cầu chọn giữa SDK `google-genai` và `httpx` gọi REST,
dựa trên 5 tiêu chí: tắt được retry của SDK không, cách khai báo schema, cách lấy usage, có dễ thay
bằng bản giả không, và có kiểm soát được việc key chỉ nằm trong header không. Spec còn giới hạn tối đa
2 dependency trực tiếp, và thư viện nào được import trực tiếp đều phải khai báo.

Tài liệu được tra qua Context7 ngày 2026-11-26:

- `/googleapis/python-genai`: mã nguồn và README của SDK (nguồn chính)
- `/websites/deepwiki_googleapis_python-genai`: DeepWiki về SDK (nguồn thứ cấp)
- `/websites/ai_google_dev_gemini-api`, `/websites/ai_google_dev_api`: tài liệu chính thức của Gemini API

## So sánh theo tiêu chí

| Tiêu chí | SDK `google-genai` | REST `httpx` |
|---|---|---|
| 1. Tắt retry | Được, xem (a). PR phải chỉ ra dòng tắt | Không có retry nào để tắt. Chỉ có một vòng retry, do chương trình tự viết |
| 2. Khai báo schema | `response_json_schema=Answer.model_json_schema()` | Như nhau: gửi `generationConfig.responseJsonSchema` cùng một schema |
| 3. Lấy usage | `response.usage_metadata.prompt_token_count`…, tên đã bị SDK đổi | Đọc thẳng `usageMetadata.promptTokenCount`, `candidatesTokenCount`, `totalTokenCount`, đúng tên spec ghi |
| 4. Thay bằng bản giả | Phải giả `client.models.generate_content` và tự dựng `errors.APIError(code, response_json, response)`. Bản giả phụ thuộc vào nội bộ SDK | Truyền vào hàm `send(httpx.Request) -> httpx.Response`. Test trả về `httpx.Response(503, json=...)` hoặc ném `httpx.ReadTimeout` |
| 5. Key chỉ trong header | Chỉ chứng minh được bằng trích tài liệu, xem (b) và (c) | Test trực tiếp trên `httpx.Request` đã dựng xong, trước khi gửi: URL không chứa key, header có `x-goog-api-key` |
| Thêm: số dependency | **3** (`google-genai`, `httpx`, `pydantic`), vượt giới hạn 2. Xem giải thích bên dưới | **2** (`httpx`, `pydantic`) |

Vì sao dùng SDK lại thành 3 dependency (đây là suy luận từ mã nguồn): code retry của SDK
(`_api_client.py`, `retry_args`) nhận diện lỗi tạm thời bằng `isinstance(e, _HTTPX_TRANSIENT_EXC)`, tức là
timeout và lỗi kết nối đi ra khỏi SDK dưới dạng exception gốc của httpx. Muốn phân biệt "hết thời gian chờ 30s"
với "lỗi kết nối" như spec yêu cầu, chương trình phải `import httpx`. Theo quy tắc của spec, khi đó httpx phải
được khai báo, nên tổng là 3.

## Ba câu hỏi về SDK (để thấy SDK thua ở đâu)

**(a) Retry của SDK mặc định bật hay tắt, tắt bằng tham số nào?**
Trong mã hiện tại, không đặt `retry_options` thì SDK **không retry**:

> `if options is None: return {'stop': tenacity.stop_after_attempt(1), 'reraise': True}`
> (`google/genai/_api_client.py`, `retry_args`)

Nhưng nếu truyền `HttpRetryOptions()` mà không đặt `attempts` thì mặc định là 5 lần (`_RETRY_ATTEMPTS = 5  # including the initial call`).
Tắt tường minh bằng `HttpOptions(retry_options=HttpRetryOptions(attempts=1))`. Docstring của `attempts`:

> "Maximum number of attempts, including the original request. If 0 or 1, it means no retries. If not specified, default to 5."
> (`google/genai/types.py`, `HttpRetryOptions`)

Như vậy mặc định nào được dùng là tùy cách gọi. Giá trị này cũng có thể đổi giữa các phiên bản; ở đây mình
không ghim phiên bản SDK nào.

**(b) SDK gửi key trong header hay trong query string?**
Trong header:

> `self._http_options.headers['x-goog-api-key'] = self.api_key`
> (`google/genai/_api_client.py`, `BaseApiClient.__init__`)

**(c) Truyền `api_key=` tường minh có được ưu tiên hơn `GOOGLE_API_KEY` trong môi trường không?**
Tài liệu chính chỉ nói về thứ tự giữa hai biến môi trường:

> "It's recommended that you set only one of those variables, but if both are set, `GOOGLE_API_KEY` takes precedence."
> (README của `python-genai`)

Thứ tự "tham số `api_key` của constructor → `GOOGLE_API_KEY` → `GEMINI_API_KEY`" chỉ có ở DeepWiki
("Explicit configuration takes precedence"), một nguồn thứ cấp. Mình không tìm thấy câu này trong mã nguồn
hay README. Câu trả lời là "có thể có, nhưng chưa được tài liệu chính xác nhận". Với REST, câu hỏi này
không tồn tại: không có code nào tự đọc biến môi trường.

## Quyết định

Gọi Gemini qua REST bằng `httpx`, kiểm tra schema bằng `pydantic`. Hai lý do, theo thứ tự quan trọng:

1. Tiêu chí "key chỉ nằm trong header" được chứng minh bằng test trên request đã dựng, không phải bằng trích
   tài liệu. Câu trả lời (c) ở trên cho thấy trích tài liệu không phải lúc nào cũng làm được.
2. Dùng SDK thì phải khai báo 3 dependency, vượt giới hạn 2. Lý do này yếu hơn lý do 1, vì hai điều:
   giới hạn 2 là ràng buộc do chính spec 001 đặt ra, không phải ràng buộc kỹ thuật; và việc "phải import httpx"
   là suy luận từ mã nguồn, chưa được chạy thử để xác nhận. Nếu nới giới hạn này thì SDK là một phương án hợp lý.

## Ranh giới adapter

- Chỉ `gemini.py` được import `httpx` và biết định dạng REST: URL, header `x-goog-api-key`, `usageMetadata`,
  `finishReason`, `error.details`.
- `cli.py` chỉ dùng những gì `gemini.py` công khai: `ask()`, `Answer`, `Reply`, các exception và hằng số.
  Ngoại lệ duy nhất là `run()` dựng `httpx.Client` mặc định.
- Lỗi key sai được `gemini.py` dịch thành `GeminiHTTPError.key_invalid`, nên `cli.py` không cần biết lý do
  nằm ở `error.details[].reason`.

**Đổi sang SDK = viết lại gemini.py, không đụng cli.py.**

## Hệ quả

- Phải tự viết phần dựng request và đọc response (ước chừng 30 dòng), và tự giữ đúng tên trường REST.
- PR không có "dòng tắt retry của SDK" để chỉ ra. Thay vào đó PR chỉ ra vòng retry duy nhất trong `gemini.py`.
- Test CLI dùng `ask` giả và không biết httpx. Test của `gemini.py` dùng `send` giả và được phép biết REST.

## Phương án khác đã xét

**`urllib.request` (thư viện chuẩn)**: dùng thì chỉ còn 1 dependency (`pydantic`). Bị loại vì:

- timeout và lỗi kết nối không có kiểu riêng rõ ràng: cả hai thường hiện ra dưới dạng `URLError` bọc một
  exception khác, nên phải mở lớp bọc ra mới phân loại được thành "hết thời gian chờ 30s" và "lỗi kết nối";
- lỗi HTTP là `HTTPError` được ném ra, body phải đọc từ chính exception đó. Còn `httpx` trả về một `httpx.Response`
  bình thường cho mọi mã trạng thái, nên phần đọc lỗi và phần đọc kết quả có cùng một hình dạng;
- không có sẵn kiểu response để dựng bản giả. Với `httpx`, test chỉ cần `httpx.Response(503, json=...)`.

Tiết kiệm được một dependency không bù được phần code phân loại lỗi và phần code dựng bản giả phải tự viết thêm.

## Khi nào xem lại

Viết ADR mới để cân nhắc chuyển sang SDK (khi đó chỉ `gemini.py` thay đổi) nếu cần một trong những thứ sau:

- streaming;
- Live API;
- upload file;
- context caching;
- chạy trên Vertex AI;
- phần request/response tự bảo trì trong `gemini.py` vượt khoảng 100 dòng.
