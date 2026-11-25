@pyproject.toml và uv.lock khác nhau thế nào? Vì sao phải commit cả hai?
Khác nhau thế nào
pyproject.toml	uv.lock
Ai viết	Bạn viết tay, hoặc dùng uv add	uv tự sinh ra, không sửa tay
Nội dung	Bạn cho phép dùng phiên bản nào (một khoảng)	Phiên bản cụ thể đã chọn
Phạm vi	Chỉ các dependency trực tiếp	Toàn bộ cây dependency, kể cả gói con
Ví dụ	pytest>=9.2.0	pytest bản X.Y.Z, kèm URL wheel và sha256
Thông tin khác	Metadata dự án, cấu hình ruff/pytest, build backend	Chỉ các gói và nguồn tải của chúng
Một ví dụ có trong project này: pyproject.toml chỉ khai báo hai gói dev là pytest và ruff. Nhưng uv.lock có thêm colorama và iniconfig, dù bạn không hề khai báo chúng. Lý do là pytest cần hai gói này (colorama chỉ dùng trên Windows). Ngoài ra, mỗi gói trong lock đều có hash = "sha256:...", nên uv kiểm tra được file tải về đúng là file đã được khoá.

Nói ngắn gọn: pyproject.toml là ý định ("tôi cần pytest từ 9.2 trở lên"), còn uv.lock là kết quả giải ("với ý định đó, hôm nay đây là bộ phiên bản cụ thể hoạt động được").

Vì sao phải commit cả hai
Commit pyproject.toml vì đây là nguồn gốc. Không có nó thì uv không biết project tên gì, cần gói nào, cũng không có cấu hình ruff hay pytest.

Commit uv.lock để mọi môi trường giống hệt nhau:

>=9.2.0 hôm nay có thể ra 9.2.0, nhưng tháng sau có thể ra 9.5.0. Nếu không có lock, máy bạn, máy đồng đội và CI có thể cài các phiên bản khác nhau. Khi đó sẽ gặp lỗi kiểu "máy tôi chạy được mà".
Có lock thì uv sync cài đúng từng byte như lần trước, kể cả các gói con như iniconfig.
Lock cũng giúp phát hiện gói bị thay đổi trên registry, vì hash sẽ không khớp.
Khi bạn chủ động nâng phiên bản (uv lock --upgrade), diff của uv.lock trong PR cho thấy rõ gói nào đổi từ bản nào sang bản nào, nên dễ review.
Commit cả hai cùng lúc vì chúng phải khớp nhau. Nếu bạn sửa pyproject.toml mà không cập nhật lock, uv sync --locked (thường dùng trong CI) sẽ báo lỗi lock đã lỗi thời. Đó là tín hiệu tốt: nó không cho hai file lệch nhau mà không ai biết.

★ Insight ─────────────────────────────────────

Trong lock, labor-law-assistant có source = { editable = "." }: project của bạn được cài ở chế độ editable. Nhờ vậy khi sửa code trong src/, bạn không cần cài lại.
Phần [package.metadata.requires-dev] trong lock chép lại các specifier >=9.2.0 từ pyproject.toml. uv dùng phần này để kiểm tra nhanh xem lock còn khớp với pyproject.toml không, mà không cần giải lại toàn bộ dependency.
Có một ngoại lệ hay gặp: nếu bạn viết thư viện để publish lên PyPI, người dùng thư viện đó không dùng uv.lock của bạn, chỉ dùng các khoảng phiên bản trong pyproject.toml. Với ứng dụng như labor-law-assistant thì lock là bắt buộc.
─────────────────────────────────────────────────
Hiện cả hai file đều đang ở trạng thái untracked (?? labor-law-assistant/). Nếu muốn, mình có thể commit chúng giúp bạn.
Vì sao dùng src/ layout? Nếu bỏ thư mục src/ thì điều gì thay đổi?
Vì sao dùng src/ layout
1. Tests chạy trên package đã được cài, không chạy trên thư mục tình cờ nằm cạnh.

Python tự thêm thư mục hiện tại (cwd) vào sys.path khi bạn chạy python, python -m pytest hoặc mở REPL. Ở flat layout, thư mục labor_law_assistant/ nằm ngay tại root. Vì vậy from labor_law_assistant import health trong tests/test_health.py có thể import thẳng từ thư mục đó, bỏ qua bước cài đặt.

Với src layout, root không chứa package nào. Python chỉ tìm thấy package qua file .pth mà uv sync tạo ra, tức là qua đúng con đường người dùng thật sẽ đi.

2. Lỗi đóng gói lộ ra sớm. Ví dụ bạn quên đưa py.typed hoặc một file data vào wheel, hoặc cấu hình build sai. Ở flat layout, tests vẫn pass vì chúng đọc thẳng source tree, rồi người khác cài wheel thì hỏng. src layout giảm khả năng tests pass "nhờ may mắn" như vậy.

3. Chỉ code của package mới import được. .pth trỏ vào src/, nên chỉ những gì trong src/ mới thành module top-level. Các thư mục tests/, scripts/… ở root không bị lộ ra thành thứ import được.

Nếu bỏ src/ thì điều gì thay đổi
Giả sử bạn chuyển src/labor_law_assistant/ thành labor_law_assistant/ ngay tại root:

Build sẽ hỏng nếu không sửa cấu hình. uv_build mặc định tìm module ở src/. Bạn phải thêm vào pyproject.toml:


[tool.uv.build-backend]
module-root = ""
Thiếu dòng này thì uv sync hoặc uv build sẽ báo không tìm thấy module labor_law_assistant.

File .pth sẽ trỏ vào root của project, không còn trỏ vào src/. Mọi thư mục ở root đều có thể import được dưới dạng module top-level. Ví dụ tests (nếu sau này bạn thêm __init__.py) có thể đụng tên với package tests của thư viện khác.

Hai đường import cùng tồn tại. Chạy uv run pytest thì package được tìm qua .pth. Chạy python -m pytest hoặc python từ root thì package được tìm qua cwd. Hôm nay hai đường cho cùng kết quả vì đều là editable. Nhưng khi bạn test với wheel thật (CI, uv build rồi cài), hành vi có thể khác.

Ưu điểm của flat layout: đường dẫn ngắn hơn, và có thể python -c "import labor_law_assistant" mà không cần cài. Với một script nhỏ không bao giờ đóng gói thì flat layout hoàn toàn ổn.

Khuyến nghị: giữ src/. Project này đã có build backend, có py.typed (tức là định phân phối kèm type hints) và có test suite. Đây đúng là trường hợp src layout phát huy tác dụng.

★ Insight ─────────────────────────────────────

py.typed là file đánh dấu theo PEP 561, báo cho mypy/pyright biết package có type hints. Đây chính là loại file dễ bị bỏ sót khi đóng gói, và flat layout sẽ che mất lỗi đó trong lúc chạy tests.
tests/ của bạn không có __init__.py. Với import mode mặc định (prepend), pytest chỉ thêm tests/ vào sys.path, không thêm root. Vì vậy hiện tại uv run pytest import được package hoàn toàn nhờ .pth, đúng như src layout muốn.
Editable install không copy code mà chỉ thêm một đường dẫn qua .pth. Do đó sửa code trong src/ là có hiệu lực ngay. Chỉ khi đổi metadata, ví dụ thêm entry point, bạn mới cần uv sync lại.
─────────────────────────────────────────────────
Test hiện tại kiểm tra hành vi gì? Nếu hàm health() trả về "OK" viết hoa thì test có đỏ không?
Test kiểm tra gì

from labor_law_assistant import health

def test_health_returns_ok():
    assert health() == "ok"
Package import được. Dòng from labor_law_assistant import health chạy ở thời điểm pytest thu thập test. Nếu package chưa được cài, tức là thiếu file .pth như đã nói ở câu trước, test sẽ lỗi ngay ở bước collect, chưa kịp chạy assert.
health có tồn tại và gọi được mà không cần đối số.
Giá trị trả về bằng đúng chuỗi "ok". Đây là hành vi chính mà test khẳng định.
Những gì test không kiểm tra: kiểu trả về có thực sự là str không (annotation -> str không được kiểm tra lúc chạy), và hàm có side effect hay không.

Nếu trả về "OK" thì test có đỏ không?
Có, test sẽ đỏ. Phép so sánh == giữa hai chuỗi trong Python phân biệt hoa thường, và "OK" == "ok" là False. Pytest sẽ báo đại khái như sau:


>       assert health() == "ok"
E       AssertionError: assert 'OK' == 'ok'
E         - ok
E         + OK
(Mình không sửa code để chạy thử, nên đây là định dạng điển hình của pytest chứ không phải output thật. Nếu bạn muốn, mình có thể đổi tạm rồi hoàn tác.)

Đây là hành vi đúng: test đang khoá một hợp đồng chính xác. Nếu sau này có endpoint hoặc health check nào so sánh với "ok", thì đổi sang "OK" là thay đổi phá vỡ tương thích, và test bắt được đúng điều đó.

★ Insight ─────────────────────────────────────

Pytest hiện được diff 'OK' == 'ok' chi tiết, dù bạn chỉ viết assert thuần, là nhờ assertion rewriting. Pytest viết lại AST của file test lúc import, nên không cần assertEqual như unittest. File .pyc có tên test_health.cpython-314-pytest-9.2.0.pyc trong __pycache__ chính là bản đã được viết lại, nên tên file mới có chữ pytest-9.2.0.
Nếu bạn muốn chấp nhận cả hai cách viết thì phải nói rõ trong test, ví dụ assert health().lower() == "ok". Nhưng như vậy là nới lỏng hợp đồng. Nên chọn cách đó chỉ khi hệ thống phía sau thật sự không phân biệt hoa thường.
─────────────────────────────────────────────────
Project này đang dùng vector database nào để lưu văn bản luật?
Hiện chưa có vector database nào. Project mới chỉ là bộ khung ban đầu, chưa có code nào lưu hoặc truy vấn văn bản luật. Mình kiểm tra như sau:

Dependencies: trong pyproject.toml, dependencies = [] trống. Chỉ có hai gói dev là pytest và ruff. Trong uv.lock cũng không có Chroma, Qdrant, FAISS, pgvector, LanceDB hay thư viện tương tự.
Code: toàn bộ source chỉ là src/labor_law_assistant/init.py, trong đó có đúng hàm health() trả về "ok".
Tìm kiếm: grep các từ khoá chroma|qdrant|faiss|pinecone|weaviate|milvus|pgvector|lancedb|vector|embedding trên toàn project (trừ .venv) không ra kết quả nào.
Cấu hình: .env.example chỉ có GEMINI_API_KEY=. Có vẻ bạn định dùng Gemini làm LLM (và có thể cả làm embedding), nhưng chưa có code nào dùng đến key này. Mình chỉ đọc .env.example, không mở .env vì file đó chứa secret.
Còn một khả năng khác: trên máy bạn có một project khác ở /home/nlhdang/projects/Labor-Law-Agent. Nếu câu hỏi của bạn là về project đó thì mình có thể kiểm tra giúp.

★ Insight ─────────────────────────────────────

Đây là lúc tốt để chọn vector DB, vì chưa có code nào phụ thuộc vào nó. Với văn bản luật, thường cần lọc theo metadata như số hiệu văn bản, điều, khoản, ngày hiệu lực. Vì vậy nên ưu tiên store hỗ trợ lọc metadata tốt, chứ không chỉ tìm theo độ tương đồng.
Project này có thư mục .git riêng, tức là một repo lồng bên trong workspace_vibecoding. Đó là lý do repo ngoài chỉ thấy cả thư mục là ?? labor-law-assistant/. Nếu bạn muốn commit pyproject.toml và uv.lock như đã nói lúc đầu, cần commit trong repo bên trong, hoặc quyết định có dùng submodule hay không.
─────────────────────────────────────────────────
Cách bảo vệ, xếp từ yếu đến mạnh
1. .gitignore: đã có, nhưng có ba điểm cần biết

Chỉ áp dụng cho file chưa được track. Nếu .env từng được commit, thêm vào .gitignore sau đó không có tác dụng gì.
git add -f .env bỏ qua .gitignore hoàn toàn.
Pattern .env không bắt được .env.local hay .env.production. Pattern chắc hơn là:

.env*
!.env.example
2. Tự kiểm tra trước khi commit

Hạn chế dùng git add -A hoặc git add . một cách mù quáng. Trước khi commit, xem lại git diff --cached --name-only.
Khi nghi ngờ, chạy git check-ignore -v <file> để xác nhận.
3. Pre-commit hook quét secret: đây là lớp thật sự chặn được lỗi
Dùng gitleaks hoặc detect-secrets qua framework pre-commit. Hook quét nội dung chứ không chỉ tên file. Nhờ vậy, nếu bạn lỡ dán key vào config.py thì nó vẫn bắt được.

4. Phía server (khi có remote)
Bật secret scanning và push protection trên GitHub. GitHub sẽ từ chối push nếu phát hiện key của các provider nó nhận diện được.

Nếu lỡ commit rồi
Bước 0, làm trước mọi thứ khác: thu hồi key. Vào Google AI Studio, revoke GEMINI_API_KEY rồi tạo key mới. Nếu commit đã được push lên remote công khai, hãy coi key đó đã bị lộ. Bot quét GitHub tìm key chỉ mất vài phút. Xoá lịch sử chỉ là dọn dẹp, đổi key mới là cách khắc phục thật sự.

Sau đó, tuỳ tình huống:

Tình huống	Cách xử lý
Chưa push, nằm ở commit cuối	git rm --cached .env rồi git commit --amend
Chưa push, nằm ở commit cũ hơn	git rebase -i để sửa commit đó, hoặc dùng git filter-repo
Đã push	git filter-repo --path .env --invert-paths, sau đó git push --force. Mọi người cần clone lại repo. Bản sao vẫn có thể còn trong fork, PR hoặc cache của GitHub, nên phải liên hệ GitHub Support nếu cần xoá hẳn.
Lưu ý: chỉ chạy git rm --cached .env rồi commit là chưa đủ. Lệnh đó chỉ làm Git ngừng track file từ commit đó trở đi, còn key vẫn nằm trong lịch sử.

★ Insight ─────────────────────────────────────

--cached nghĩa là chỉ xoá khỏi index, file .env trên đĩa vẫn giữ nguyên. Thiếu cờ này thì git rm xoá luôn file thật của bạn.
Project đã có cặp .env / .env.example, đây là pattern đúng. .env.example được commit để ghi lại cần những biến nào, còn .env giữ giá trị. Pattern .env* kèm !.env.example giữ đúng ranh giới đó.
Git đọc .gitignore từ trên xuống, dòng sau ghi đè dòng trước. Vì vậy dòng phủ định !.env.example phải đặt sau .env* thì mới có tác dụng.
─────────────────────────────────────────────────
Mình chưa sửa gì. Mình có thể làm giúp bạn một hoặc cả hai việc sau:

Đổi .gitignore sang .env* / !.env.example.
Thêm cấu hình pre-commit với gitleaks (cái này thêm một dev dependency).
Bạn muốn làm việc nào?