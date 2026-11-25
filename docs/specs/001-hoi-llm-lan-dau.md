# 001: Hỏi LLM lần đầu

## Vì sao cần
Người lao động hoặc nhân viên nhân sự cần hỏi nhanh một câu về luật lao động Việt Nam
từ dòng lệnh và nhận câu trả lời có cấu trúc. Đây là lần đầu project gọi LLM. Spec RAG sau
này sẽ thêm văn bản luật vào chính lời gọi này, nên hình dạng đầu ra và cách xử lý lỗi chốt
ở đây sẽ được dùng lại.

Lưu ý: ở spec này model trả lời **bằng kiến thức có sẵn của nó**, chưa có văn bản luật làm căn cứ.

## Hành vi mong muốn

### Gọi lệnh

    uv run --env-file .env lla ask <câu hỏi>

- `<câu hỏi>` có thể gồm nhiều từ, có hoặc không có dấu nháy. Các từ được nối lại bằng
  một dấu cách.
- Gõ sai cú pháp (`lla`, `lla ask` không có câu hỏi, lệnh con lạ): để argparse tự in
  hướng dẫn sử dụng ra stderr theo định dạng của nó (không theo mẫu `Lỗi: ...`), exit 2.
- Chuẩn hóa câu hỏi: chuyển sang Unicode NFC rồi bỏ khoảng trắng ở hai đầu. Bản đã chuẩn
  hóa là bản được kiểm tra độ dài, được gửi lên API, và là bản dùng để tính số N trong
  thông báo lỗi. Độ dài đếm bằng `len()` của Python, tối đa 2000.

### Cấu hình
- `GEMINI_API_KEY`: bắt buộc. Rỗng hoặc chỉ có khoảng trắng cũng tính là thiếu.
  Chỉ đọc biến này, không đọc `GOOGLE_API_KEY` hay biến nào khác. Key được truyền
  tường minh vào client.
- `GEMINI_MODEL`: không bắt buộc. Rỗng hoặc chỉ có khoảng trắng thì dùng model mặc định.
- Key chỉ được gửi trong header (`x-goog-api-key`), **không bao giờ** nằm trong URL.

### Lời gọi
- Gọi Gemini **đúng 1 lần** nếu không có lỗi. Yêu cầu model trả lời theo JSON schema
  gồm `answer`, `in_scope` và `confidence`.
- System instruction phải yêu cầu model:
  - luôn trả lời bằng tiếng Việt, kể cả khi câu hỏi viết bằng ngôn ngữ khác;
  - chỉ trả lời về luật lao động Việt Nam;
  - nếu câu hỏi ngoài phạm vi thì đặt `in_scope = false` và viết một câu từ chối ngắn;
  - trả lời ngắn gọn nhưng nêu đủ mọi trường hợp, khoảng 200 từ. Khi hai yêu cầu này va nhau,
    **nêu đủ trường hợp thắng**: một câu trả lời luật bỏ sót một nhánh còn nguy hiểm hơn một
    câu trả lời dài.
  Nội dung chính xác của prompt do Claude Code đề xuất ở bước Plan, đặt trong một file
  riêng để dễ review.
- Chỉ có **một lớp retry**, là retry của chương trình. Nếu dùng SDK có retry riêng thì
  phải tắt retry đó đi.

### Đầu ra khi thành công
In ra stdout **một object JSON trên một dòng**, có newline ở cuối, UTF-8, không escape
tiếng Việt. Exit 0. Các ví dụ bên dưới xuống dòng chỉ để dễ đọc.

| Trường | Kiểu | Ý nghĩa | Ai tạo ra |
|---|---|---|---|
| `answer` | str, không rỗng | Câu trả lời, hoặc câu từ chối nếu ngoài phạm vi | Model |
| `in_scope` | bool | Câu hỏi có thuộc luật lao động Việt Nam không | Model |
| `confidence` | `"high"` \| `"medium"` \| `"low"` | Model tự đánh giá. Chỉ là nhãn tham khảo, KHÔNG phải xác suất | Model |
| `model` | str | Phiên bản model API báo đã dùng. Nếu API không trả thì là tên chương trình đã gửi đi | Chương trình |
| `usage.input_tokens` | int \| null | Lấy từ `promptTokenCount` | API |
| `usage.output_tokens` | int \| null | Lấy từ `candidatesTokenCount`. Không gồm token suy nghĩ | API |
| `usage.total_tokens` | int \| null | Lấy từ `totalTokenCount`, KHÔNG tự cộng. Có thể lớn hơn input + output vì gồm cả token suy nghĩ; đây là hành vi đúng | API |

Chương trình **kiểm tra lại** phần model trả về theo schema:
- sai kiểu (ví dụ `"in_scope": "true"`), `confidence` ngoài 3 giá trị, hoặc `answer`
  rỗng sau khi bỏ khoảng trắng: coi là phản hồi hỏng, exit 4;
- có thêm trường lạ: bỏ qua, không đưa ra đầu ra.

`usage` luôn là một object có đủ 3 trường con. Nếu API không trả usage, hoặc thiếu một trường
con, thì trường con đó có giá trị `null` và **vẫn exit 0**. Không bao giờ thay bằng 0. Ghi đúng
**một dòng** cảnh báo ra stderr, liệt kê mọi trường thiếu:
`Cảnh báo: API không trả số token: input_tokens, total_tokens`.

Ví dụ 1, câu hỏi đúng phạm vi:

    $ uv run --env-file .env lla ask "Nghỉ việc phải báo trước bao nhiêu ngày?"
    {"answer": "Theo Điều 35 Bộ luật Lao động 2019, ...", "in_scope": true,
     "confidence": "high", "model": "<model>",
     "usage": {"input_tokens": 182, "output_tokens": 140, "total_tokens": 410}}
    exit 0

Ví dụ 2, câu hỏi ngoài phạm vi. Câu từ chối do model viết, nên mỗi lần chạy có thể khác:

    $ uv run --env-file .env lla ask Cách nấu phở bò
    {"answer": "Mình chỉ hỗ trợ câu hỏi về luật lao động Việt Nam.", "in_scope": false, ...}
    exit 0

Ví dụ 3, thiếu key:

    $ uv run lla ask "Lương tối thiểu vùng 1?"
    stderr: Lỗi: chưa có GEMINI_API_KEY. Copy .env.example thành .env rồi điền key.
    exit 2

### Lỗi

stdout chỉ chứa JSON khi thành công. Khi thất bại thì stdout để trống. stderr dùng cho
mọi thông báo phụ: lỗi, cảnh báo, dòng báo đang thử lại.

Ý nghĩa exit code, dùng để xếp mọi lỗi mới (kể cả ở các spec sau):

- **0**: thành công, kể cả khi câu hỏi ngoài phạm vi hoặc thiếu usage.
- **1**: bug của chương trình, kể cả khi API báo request do chương trình dựng ra không hợp lệ.
- **2**: người dùng tự sửa được (đầu vào, cú pháp, key, tên model).
- **3**: lỗi phía dịch vụ (tạm thời hoặc không), người dùng chỉ có thể chờ hoặc báo lỗi.
- **4**: có phản hồi nhưng không dùng được.
- **130**: người dùng ngắt.

Mỗi lần thử được phân loại riêng. Gặp lỗi **không retry được** thì dừng ngay và báo theo
lỗi đó, kể cả khi các lần trước bị lỗi khác. Ví dụ: lần 1 bị 503, lần 2 bị 400, thì dừng
ở lần 2 và báo HTTP 400.

| Nhóm | Gồm | Retry? | Người dùng thấy (stderr) | exit |
|---|---|---|---|---|
| Đầu vào / cấu hình | thiếu key, câu hỏi rỗng, câu hỏi quá 2000 ký tự | Không gọi API | Lỗi: <mô tả cụ thể> | 2 |
| Sai cú pháp lệnh | `lla`, `lla ask` không có câu hỏi, lệnh con lạ | Không gọi API | Hướng dẫn sử dụng của argparse | 2 |
| Key hoặc model sai | HTTP 401; HTTP 403; HTTP 404; HTTP 400 có lý do `API_KEY_INVALID` (Gemini thường báo key sai bằng 400) | Không | Lỗi từ Gemini (HTTP <mã>): <message>. Thêm gợi ý: 401 và 400-key → "Kiểm tra GEMINI_API_KEY."; 403 → "Kiểm tra GEMINI_API_KEY, và API đã được bật hay khu vực có được hỗ trợ không."; 404 → "Kiểm tra GEMINI_MODEL." | 2 |
| Lỗi tạm thời | HTTP 408, 429, 500, 502, 503, 504, timeout, lỗi kết nối | Có, tối đa 3 lần | Lỗi: Gemini không phản hồi sau 4 lần thử (<lỗi cuối>) | 3 |
| Request không hợp lệ | Mọi mã 4xx còn lại, gồm 400 không phải lỗi key | Không | Lỗi chương trình: Gemini từ chối request (HTTP <mã>): <message> | 1 |
| Lỗi dịch vụ khác | Mọi mã 5xx không retry (501, ...) | Không | Lỗi từ Gemini (HTTP <mã>): <message> | 3 |
| Bị chặn | có `blockReason`, không có candidate, hoặc `finishReason` thuộc nhóm an toàn (`SAFETY`, `RECITATION`, `PROHIBITED_CONTENT`, `BLOCKLIST`, `SPII`) | Không | Lỗi: phản hồi bị chặn (<giá trị enum gốc>) | 4 |
| Bị cắt | `finishReason = MAX_TOKENS` | Không | Lỗi: phản hồi bị cắt vì hết giới hạn token | 4 |
| Phản hồi hỏng | JSON không parse được, sai schema, hoặc `finishReason` có giá trị khác `STOP` và không thuộc các nhóm trên. Nếu không có `finishReason` mà JSON hợp lệ thì coi như `STOP`, tức là thành công | Không | Lỗi: phản hồi của model không đúng định dạng (<finishReason nếu có>) | 4 |
| Ngoài dự kiến | mọi exception khác (bug) | Không | Lỗi không mong đợi: <tên loại exception>: <chi tiết>. `<chi tiết>` là message của exception. Không in traceback | 1 |
| Ctrl-C | người dùng ngắt lệnh | Không | (một dòng: Đã hủy) | 130 |

- **Che key** áp dụng cho **mọi** đầu ra, cả stdout lẫn stderr: chuỗi key được thay bằng `***`.
- **Cắt chuỗi** áp dụng cho mọi phần được chèn vào thông báo lỗi (`<message>`, `<lỗi cuối>`,
  `<chi tiết>`), cắt còn tối đa 300 ký tự. `answer` không bao giờ bị cắt. `<message>` là
  trường message rút ra từ phản hồi lỗi của API, không phải JSON thô.
- Thứ tự: che key **trước**, cắt **sau**. Làm ngược lại thì một key bị cắt ngang sẽ không khớp
  mẫu che, và nửa đầu của key lọt ra ngoài.
- Retry: chờ 1s, 2s, 4s, cố định. Không dùng header `Retry-After` ở spec này.
- Timeout 30s cho **mỗi lần thử**. Trường hợp xấu nhất lệnh chạy khoảng 2 phút; chấp
  nhận được với một lệnh CLI.
- Mỗi lần thử lại ghi một dòng ra stderr:
  `Đang thử lại (2/3) sau 2s: HTTP 503`, `... hết thời gian chờ 30s`, `... lỗi kết nối`.

## Tiêu chí chấp nhận
- [ ] Mỗi ví dụ và mỗi nhóm trong bảng lỗi có ít nhất 1 test
- [ ] Test **không gọi mạng thật** và **không ngủ thật**: phần gọi Gemini và hàm chờ được
      truyền vào từ ngoài (dependency injection), test thay bằng bản giả
- [ ] Test retry kiểm tra: luôn lỗi 503 thì gọi 4 lần với thời gian chờ [1, 2, 4]; lần 2
      thành công thì gọi 2 lần; lỗi 400 thì gọi 1 lần; 503 rồi 400 thì gọi 2 lần và báo HTTP 400 (exit 1);
      mỗi lần thử lại có đúng 1 dòng stderr đúng mẫu `Đang thử lại (n/3) sau Xs: <lý do>`
- [ ] 401, 403, 404 và 400 có lý do `API_KEY_INVALID` thì exit 2, kèm đúng gợi ý; 400 thường thì exit 1;
      501 thì exit 3 (mỗi ca có test). Plan xác nhận qua tài liệu cách Gemini báo key sai
- [ ] Sai cú pháp lệnh: test chỉ kiểm exit 2 và stdout trống, không kiểm câu chữ của argparse
- [ ] Bản PR ghi rõ retry của SDK được tắt ở dòng nào (nếu dùng SDK)
- [ ] Khi thành công: stdout là đúng 1 dòng, parse được bằng `json.loads`, đúng các trường
      và kiểu ở bảng trên
- [ ] Phản hồi sai schema (sai kiểu, `confidence` lạ, `answer` rỗng) thì exit 4, mỗi trường
      hợp có test
- [ ] Thiếu usage hoặc thiếu một trường usage thì trường đó là `null`, có đúng 1 dòng cảnh báo
      liệt kê các trường thiếu, exit 0 (có test)
- [ ] Câu trả lời dài hơn 300 ký tự được in đầy đủ, không bị cắt (có test)
- [ ] Không có `finishReason` nhưng JSON hợp lệ thì thành công (có test)
- [ ] Key không xuất hiện trong stdout hay stderr, kể cả khi thông báo lỗi giả lập có chứa
      chuỗi key (có test), và cả khi key nằm vắt qua vị trí ký tự thứ 300 (có test)
- [ ] Exception lạ thì exit 1, không có traceback (có test)
- [ ] Chuẩn hóa NFC trước khi đếm, có 2 test:
      (a) một câu ở dạng NFD có `len` > 2000 nhưng sau NFC chỉ ≤ 2000 thì được **chấp nhận**.
          Nếu chương trình không chuẩn hóa thì test này đỏ.
      (b) một câu có `len` > 2000 ngay cả sau NFC thì bị từ chối, và N trong thông báo là độ dài sau NFC
- [ ] Key chỉ nằm trong header và không đọc `GOOGLE_API_KEY`. Bằng chứng tùy cách triển khai:
      - Nếu dùng REST: test trên request đã dựng xong (trước khi gửi) cho thấy URL không chứa key
        và header có `x-goog-api-key`; test đặt `GOOGLE_API_KEY` mà không có `GEMINI_API_KEY`
        thì exit 2.
      - Nếu dùng SDK: test phần đọc cấu hình (cùng ca `GOOGLE_API_KEY` như trên); PR trích tài liệu
        tra qua Context7 trả lời Câu hỏi mở 1(b) và 1(c)
- [ ] `uv run pytest -q` và `uv run ruff check .` đều sạch
- [ ] PR có output chạy thật với key thật cho ví dụ 1 và ví dụ 2. Tiêu chí đạt khi lệnh chạy
      thành công và JSON đúng cấu trúc; nếu `in_scope` sai thì ghi nhận lại, không tính là trượt
- [ ] Thêm tối đa 2 dependency trực tiếp vào `dependencies`: client gọi Gemini và `pydantic`
      (để kiểm tra schema), và phải hỏi trước. Thư viện nào được import trực tiếp đều phải khai báo,
      kể cả khi nó đã đi kèm gián tiếp. Dùng argparse có sẵn, không thêm thư viện CLI
- [ ] Chạy thật ví dụ 1 **3 lần**, không lần nào bị `MAX_TOKENS`. PR ghi giới hạn token output
      đã chọn và lý do. Đánh giá độ tin cậy thật sự là việc của eval sau này

## Không làm trong spec này
- RAG, văn bản luật, trích dẫn Điều khoản có kiểm chứng (spec sau)
- Lịch sử hội thoại, hỏi nhiều lượt
- Streaming
- Giao diện web hoặc API HTTP
- Cache câu trả lời
- Nhiều nhà cung cấp LLM
- Đánh giá chất lượng câu trả lời (eval): độ dài, ngôn ngữ, độ đúng của `in_scope` (spec sau)
- Câu cảnh báo "không phải tư vấn pháp lý": đây là việc của giao diện
- Chế độ debug hoặc in traceback

## Câu hỏi mở
1. Gọi Gemini qua SDK `google-genai` hay qua `httpx` gọi REST? Chọn ở bước Plan của Buổi 3,
   dựa trên: tắt được retry của SDK không, cách khai báo schema, cách lấy usage,
   có dễ thay bằng bản giả không, và có kiểm soát được việc key chỉ nằm trong header không.
   Nếu nghiêng về SDK, Plan phải tra tài liệu qua Context7 (không dựa vào trí nhớ) và trả lời 3 câu:
   (a) retry của SDK mặc định bật hay tắt, tắt bằng tham số nào;
   (b) SDK gửi key trong header hay trong query string;
   (c) truyền `api_key=` tường minh có được ưu tiên hơn `GOOGLE_API_KEY` trong môi trường không.
2. Model mặc định là gì? Tra tên model hiện hành qua Context7 trước khi chọn.
3. Các tham số sinh (temperature, giới hạn token output, mức thinking): Claude Code đề xuất ở
   bước Plan, kèm lý do. Giới hạn token output phải đủ lớn để câu trả lời không bị cắt. Plan phải tra xem token suy nghĩ
   có bị tính vào giới hạn output không. Nếu có, thinking có thể dùng hết ngân sách trước khi
   model kịp viết JSON, và dòng lỗi "Bị cắt" sẽ xảy ra thường xuyên.

## Đề xuất
(Claude Code ghi vào đây, không tự làm)