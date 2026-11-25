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