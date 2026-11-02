# Highlight everything I'll read

Bộ công cụ đánh dấu phần cần đọc, giữ định dạng tài liệu gốc và tạo bản PDF/HTML để đọc trên máy.

## Bài đầu tiên: Evals FAQ

[AI Evals: Everything You Need to Know](https://hamel.dev/blog/posts/evals-faq/) của **Hamel Husain và Shreya Shankar**. Bộ đánh dấu được đối chiếu ngày **02/11/2026** với bản nguồn ghi ngày cập nhật **21/09/2026**.

| File | Dùng để làm gì |
| --- | --- |
| [hamel-evals-reading-kit.html](hamel-evals-reading-kit.html) | Công cụ mở trực tiếp trong trình duyệt, chọn PDF/HTML gốc và tạo bản highlight. |
| [hamel-evals-reading-guide.pdf](hamel-evals-reading-guide.pdf) | Hướng dẫn thao tác và lộ trình đọc có liên kết. **Đây không phải toàn văn bài đã highlight.** |
| [data/html-annotations.json](data/html-annotations.json) | Vị trí đánh dấu và dấu kiểm tra từng mục HTML. |
| [data/pdf-annotations.json](data/pdf-annotations.json) | Tọa độ highlight trên PDF, mức ưu tiên và SHA-256 của bản nguồn. |
| [tools/annotate_pdf.py](tools/annotate_pdf.py) | Tạo PDF có chú thích bằng Python. |

**Toàn văn bài không nằm trong repo.** Bạn lấy file gốc trực tiếp từ tác giả; công cụ thêm lớp đánh dấu trên máy. Mức ưu tiên là lựa chọn biên tập dành cho người làm search, RAG và agent, không phải ghi chú của tác giả.

## Cách dùng nhanh, không cần cài Python

1. Tải `hamel-evals-reading-kit.html` bằng **Download raw file** trên GitHub, rồi mở file bằng Chrome hoặc Edge.
2. Để dùng PDF, tải [PDF chính thức](https://hamel.dev/blog/posts/evals-faq/evals-faq.pdf), chọn file trong ô **PDF**, rồi bấm **Tạo PDF đã highlight**.
3. Để dùng HTML, lưu [trang gốc](https://hamel.dev/blog/posts/evals-faq/) hoặc chạy lệnh dưới đây; chọn file trong ô **HTML**, rồi bấm **Mở bản highlight**. Thanh công cụ cho phép ẩn màu, ẩn nhãn ưu tiên, **Lưu HTML** và **In / lưu PDF**.

```bash
curl -L "https://hamel.dev/blog/posts/evals-faq/" -o evals-faq.html
```

Trên Windows cmd có thể dùng `curl.exe`. File bạn chọn được xử lý trong trình duyệt, không gửi lên máy chủ. PDF hoạt động ngoại tuyến sau khi đã tải file gốc; HTML có thể cần mạng để lấy CSS, font và hình. Khi lưu HTML, công cụ thử gom tài nguyên và báo rõ nếu còn tài nguyên cần mạng.

## Màu và phạm vi đánh dấu

| Màu | Ưu tiên | Số mục |
| --- | --- | ---: |
| Vàng | Đọc kỹ | 20 |
| Xanh lá | Đọc lướt | 31 |
| Xám tím | Tra cứu khi cần | 10 |

Tổng cộng **61 câu hỏi**, **93 đoạn chọn lọc** và **61 nhãn ưu tiên**. PDF dùng chú thích có thể sửa hoặc xóa trong trình đọc hỗ trợ. Bản Python dùng vạch màu ở lề tiêu đề; bản trình duyệt tô nhẹ tiêu đề.

## Tạo PDF bằng Python

Cần Python và PyMuPDF:

```bash
python -m pip install PyMuPDF
python tools/annotate_pdf.py --download -o private/evals-faq.highlighted.pdf
```

Lệnh tải PDF trực tiếp từ tác giả vào thư mục `private/`, kiểm tra đúng phiên bản và tạo bản đánh dấu. Nếu đã có PDF gốc:

```bash
python tools/annotate_pdf.py "duong-dan/toi/ban-goc.pdf" -o private/evals-faq.highlighted.pdf
```

Đầu ra mặc định không ghi đè file đang có. Thêm `--overwrite` khi muốn tạo lại bản đánh dấu; file gốc luôn được giữ riêng. Thư mục `private/` và các tên file nguồn/kết quả thông dụng được bỏ qua bởi Git.

## Phiên bản và kiểm tra

- PDF được ghim bằng SHA-256. Nếu tác giả thay PDF, công cụ dừng trước khi tô để tránh lệch tọa độ.
- HTML được đối chiếu theo từng mục. Mục đã thay đổi hoặc không khớp sẽ được bỏ qua và báo số lượng.
- Kiểm tra bản PDF bằng Python: **93/93 vị trí** khớp duy nhất trong đúng FAQ; **61/61 tiêu đề** khớp mục lục; văn bản của **61 trang** và **69 bookmarks** được giữ nguyên.
- Đã kiểm tra hình render của các trang đại diện, gồm phần nền tảng, phân tích lỗi, RAG và agent. Kiểm tra sai phiên bản xác nhận không tạo đầu ra.

## Tạo lại file công cụ HTML

```bash
python tools/build_kit.py
```

Lệnh chỉ cần thư viện chuẩn Python, ghép template, manifest và mã JavaScript đã có trong repo thành một file HTML. Thư viện PDF cho trình duyệt được kèm sẵn tại `vendor/pdf-lib.min.js`; thông báo giấy phép của thư viện ở [vendor/pdf-lib.LICENSE.md](vendor/pdf-lib.LICENSE.md).

