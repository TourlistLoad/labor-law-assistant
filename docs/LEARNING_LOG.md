## Buổi 1: Làm quen  (2026-11-25)
1. Thay đổi này làm gì:
Trước đây CLAUDE.md chứa cả luật và mấu, PR này chỉ còn luât, mẫu chuyển về đúng chỗ, PR thêm checklist để review, siết .gitignore
2. Dữ liệu đi qua đâu:
.github/pull_request_template.md: github đọc khi có PR mới
CLAUDE.md: Claude code sẽ nạp file này vào context ở đầu mỗi session.
docs/specs/TEMPLATE.md: này chứa mẫu spec để copy mỗi lần viết spec
docs/REVIEW_CHECKLIST.md: người review đọc
.gitignore: git đọc, bỏ qua các file chưa track có trong này
3. Một quyết định thiết kế và phương án bị loại: Để mẫu trong CLAUDE.md → bị loại, vì tốn token ở mọi phiên và model có thể hiểu nhầm mẫu là luật.
4. Thứ có thể hỏng và cách đang bảo vệ:
Bắt quá rộng: .env* bắt mọi thứ có tên bắt đầu bằng .env.
git đọc từ trên xuống, dòng sau ghi đè dòng trước.
Cách bảo vệ hiện tại là đọc git status trước mỗi commit.
5. Bằng chứng nó đúng:
git check-ignore -v .env .env.local in ra cả hai file, kèm dòng .env*.
git check-ignore -v --no-index .env.example in ra dòng !.env.example.
uv run pytest -q vẫn pass
## Buổi 2: MCP Context7 (2026-11-25)
- Tra google-genai: gọi tool resolve-library-id 2 lần, tool query-docs 3 lần. và không hỏi quyền. sau đó gửi bảng plan hỏi quyền ghi từ tôi
- Gõ /context:
    MCP tools                   1.9k 0.2%
    MCP server instructions     1.8k 0.2%

1. Server này cho Claude Code thêm khả năng gì?
Thêm khả năng tra cứu internet bên ngoài. Nó chỉ có 2 tool: resolve-library-id để tìm thư viện, query-docs để lấy tài liệu của thư viện đó
2. Ai đọc .mcp.json, vào lúc nào? Kết quả tra tài liệu quay về nằm ở đâu?
claude sẽ đọc .mcp.json, vào lúc mở phiên. kết quả tra tài liệu sẽ được chèn thẳng vào context cuộc hội thoại
3. Vì sao chọn scope project mà không chọn local?
Vì local thì chỉ có tôi ở trong repo đó mới dùng được, còn project thì ai clone repo này đều dùng được
4. Thứ có thể hỏng:
MCP này là bên thứ 3 và content của nó đi thằng vào context nên nếu trong content có những dòng "hãy chạy lệnh X" thì sẽ bị lừa, có thể bị hack gì đó. Claude code có hỏi tôi có tin tưởng server này không và của nó chỉ hiện "read-only"

## Buổi 3: Chạy thật spec 001, ca eval đầu tiên (2026-11-27)
(Claude Code ghi theo output chạy thật do chủ repo dán. Nội dung luật **chưa đối chiếu văn bản gốc**.)

Lệnh: `GEMINI_MODEL=gemini-3.6-flash uv run --env-file .env lla ask <câu hỏi>`

### Model mặc định `gemini-3.8-flash` không chạy được
- Ví dụ 1 chạy 4 lần (3 lần liền nhau, 1 lần sau khi đợi khoảng 5 phút): cả 4 đều exit 3, mất 69–109s.
  Mỗi lần gặp lẫn lộn HTTP 503 ("high demand") và "hết thời gian chờ 30s".
- Ví dụ 2 và câu "thử việc": HTTP 429 ba lần, lần cuối là 503 hoặc timeout, exit 3.
- Khi đổi sang `gemini-3.6-flash` thì mọi lần đều thành công trong 9–23s.

### Ca 1: "Nghỉ việc phải báo trước bao nhiêu ngày?" (in_scope mong đợi: true)
| Lần | Thời gian | input / output / total token | Token suy nghĩ (total − in − out) |
|---|---|---|---|
| 1 | 8.8s | 542 / 441 / 1973 | 990 |
| 2 | 23.2s | 542 / 373 / 1838 | 923 |
| 3 | 15.5s | 542 / 413 / 2001 | 1046 |

Cả 3 lần: exit 0, `in_scope: true`, `confidence: high`, không bị `MAX_TOKENS`.
Cả 3 lần đều nêu (dùng làm điểm mong đợi, cần đối chiếu Điều 35 BLLĐ 2019 và Điều 7 NĐ 145/2020/NĐ-CP):
- HĐLĐ không xác định thời hạn: ít nhất 45 ngày; từ 12 đến 36 tháng: 30 ngày; dưới 12 tháng: 03 ngày làm việc.
- Ngành, nghề đặc thù: 120 ngày (HĐLĐ không xác định thời hạn hoặc từ 12 tháng trở lên); 1/4 thời hạn (dưới 12 tháng).
- 6 trường hợp không cần báo trước: không được bố trí đúng công việc; không được trả đủ hoặc đúng hạn tiền lương;
  bị ngược đãi, quấy rối tình dục, cưỡng bức lao động; lao động nữ mang thai nghỉ theo chỉ định y tế;
  đủ tuổi nghỉ hưu; NSDLĐ cung cấp thông tin không trung thực.

Khác nhau giữa 3 lần (đây là chỗ eval cần bắt):
- Ví dụ ngành đặc thù: lần 1 có "hệ thống bán buôn/bán lẻ điện năng", lần 2 và 3 không có mà nêu "người quản lý doanh nghiệp".
  **Cần kiểm chứng** xem Điều 7 NĐ 145 có ngành điện không, vì có thể đây là chi tiết model bịa ra.
- "Đủ tuổi nghỉ hưu": lần 1 và 3 có "trừ có thỏa thuận khác", lần 2 bỏ mất ý này.
- Hình thức: lần 2 viết liền một đoạn, lần 1 và 3 xuống dòng bằng `\n`. Lần 3 trích thêm "Khoản 2 Điều 35".

### Ca 2: "Cách nấu phở bò" (in_scope mong đợi: false)
- exit 0, `in_scope: false`, `confidence: high`, token 536 / 31 / 765.
- answer: "Tôi chỉ hỗ trợ giải đáp các câu hỏi về pháp luật lao động Việt Nam."

### Ca 3: "Thử việc tối đa bao lâu?" (in_scope mong đợi: true)
- exit 0, `in_scope: true`, `confidence: high`, token 539 / 265 / 1753. Lần này không đo thời gian.
- Nêu (cần đối chiếu Điều 24, 25 BLLĐ 2019): chỉ thử việc 1 lần cho một công việc; tối đa 180 ngày với người quản lý
  doanh nghiệp; 60 ngày với công việc cần trình độ cao đẳng trở lên; 30 ngày với trung cấp, công nhân kỹ thuật,
  nhân viên nghiệp vụ; 6 ngày làm việc với công việc khác; không thử việc với HĐLĐ dưới 1 tháng (khoản 3 Điều 24).

### Kiểm tra khác trong cùng lần chạy
- Không có key: exit 2, đúng thông báo. Key sai `sai-key-thu`: HTTP 400 kèm gợi ý "Kiểm tra GEMINI_API_KEY.", exit 2,
  và chuỗi key không bị in ra.
- Khi thất bại, stdout để trống, nên lệnh pipe `| python3 -m json.tool` báo `Expecting value`; đây là hành vi đúng.
  Chữ Việt bị escape thành `\u...` là do `json.tool` mặc định dùng `ensure_ascii`; bản thân `lla` không escape.