#!/usr/bin/env python3
"""Build the source-free, two-page reading navigation PDF.

Optional rebuild dependencies: reportlab, plus NotoSans Regular/Bold fonts.
Run from any directory: python tools/build_guide.py --font-dir /path/to/fonts
The guide contains navigation and usage instructions, not the source article.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://hamel.dev/blog/posts/evals-faq/"
SOURCE_PDF = SOURCE + "evals-faq.pdf"
INK = colors.HexColor("#173C43")
TEXT = colors.HexColor("#25383C")
MUTED = colors.HexColor("#60747A")
TEAL = colors.HexColor("#17666B")
RULE = colors.HexColor("#DCE5E5")
PAPER = colors.HexColor("#F4F7F7")
PALETTE = {
    "deep": colors.HexColor("#ffec83"),
    "skim": colors.HexColor("#bdebd9"),
    "reference": colors.HexColor("#dfe5f3"),
}
FONT_DIRS = (
    Path("/opt/codex/runtimes/codex-primary-runtime/dependencies/native/"
         "libreoffice-headless/libreoffice/share/fonts/truetype"),
    Path("/usr/share/fonts/truetype/noto"),
    Path("/usr/share/fonts/noto"),
)


def register_fonts(requested: Path | None) -> None:
    candidates = [requested] if requested else list(FONT_DIRS)
    for directory in candidates:
        if directory is None:
            continue
        regular = directory / "NotoSans-Regular.ttf"
        bold = directory / "NotoSans-Bold.ttf"
        if regular.is_file() and bold.is_file():
            pdfmetrics.registerFont(TTFont("Guide", str(regular)))
            pdfmetrics.registerFont(TTFont("Guide-Bold", str(bold)))
            pdfmetrics.registerFontFamily(
                "Guide", normal="Guide", bold="Guide-Bold",
                italic="Guide", boldItalic="Guide-Bold",
            )
            return
    raise SystemExit("Provide --font-dir containing NotoSans-Regular.ttf and NotoSans-Bold.ttf")


def para(c, text, x, top, width, size=9.5, leading=14, color=TEXT, bold=False):
    style = ParagraphStyle(
        "guide", fontName="Guide-Bold" if bold else "Guide",
        fontSize=size, leading=leading, textColor=color,
        spaceBefore=0, spaceAfter=0, allowWidows=0, allowOrphans=0,
    )
    p = Paragraph(text, style)
    _, height = p.wrap(width, 1000)
    p.drawOn(c, x, top - height)
    return top - height


def label(c, text, x, y, size=10, color=TEXT, bold=False):
    c.setFillColor(color)
    c.setFont("Guide-Bold" if bold else "Guide", size)
    c.drawString(x, y, text)


def link(c, text, url, x, y, size=9, bold=False):
    font = "Guide-Bold" if bold else "Guide"
    label(c, text, x, y, size=size, color=TEAL, bold=bold)
    width = pdfmetrics.stringWidth(text, font, size)
    c.setStrokeColor(TEAL)
    c.setLineWidth(0.45)
    c.line(x, y - 2, x + width, y - 2)
    c.linkURL(url, (x, y - 3, x + width, y + size + 2), relative=0, thickness=0)


def panel(c, x, top, width, height, fill=PAPER, radius=9):
    c.setFillColor(fill)
    c.roundRect(x, top - height, width, height, radius, stroke=0, fill=1)


def footer(c, number, width):
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(42, 43, width - 42, 43)
    label(c, "READING GUIDE  /  02/11/2026", 42, 28, size=7.4, color=MUTED)
    c.setFont("Guide", 7.4)
    c.setFillColor(MUTED)
    c.drawRightString(width - 42, 28, f"{number} / 2")


def page_one(c, manifest, headings):
    width, height = A4
    left, content = 42, width - 84
    label(c, "READING KIT  /  02/11/2026", left, height - 44, 8.3, TEAL, True)
    label(c, "Evals FAQ", left, height - 86, 29, INK, True)
    label(c, "Bản đồ đọc", left, height - 116, 21, INK)
    label(c, "Bài gốc: Hamel Husain & Shreya Shankar", left, height - 141, 9.2, MUTED)
    link(c, "Mở bài gốc trên hamel.dev", SOURCE, left, height - 160, 8.7)

    panel(c, left, 663, content, 45)
    para(c, "<b>Hướng dẫn điều hướng và sử dụng.</b> Hai trang này giúp chọn mục cần đọc "
         "và tạo bản có highlight từ nguồn của tác giả; không chứa toàn văn bài.",
         left + 13, 653, content - 26, size=9.2, leading=13)

    gap = 10
    card_w = (content - 2 * gap) / 3
    priorities = (
        ("deep", "P1 / ĐỌC KỸ", 20),
        ("skim", "P2 / ĐỌC LƯỚT", 31),
        ("reference", "P3 / TRA CỨU", 10),
    )
    for idx, (key, title, count) in enumerate(priorities):
        x = left + idx * (card_w + gap)
        panel(c, x, 606, card_w, 62, PALETTE[key])
        label(c, title, x + 12, 588, 8.2, INK, True)
        label(c, str(count), x + 12, 559, 23, INK, True)
        label(c, "mục", x + 49, 562, 9.1, INK)

    label(c, "Lộ trình 6 điểm dừng", left, 520, 14, INK, True)
    label(c, "Mở đúng mục trên web hoặc nhảy tới trang PDF gốc.", left, 503, 8.6, MUTED)
    route = [
        (7, "Bắt đầu từ lỗi thực tế"),
        (10, "Chọn dữ liệu theo mục đích"),
        (26, "Kiểm tra độ tin cậy của judge"),
        (56, "Áp dụng cho search / RAG"),
        (61, "Áp dụng cho agent"),
        (49, "Đưa vào vòng phát triển"),
    ]
    top, row_h = 490, 34
    for idx, (ordinal, name) in enumerate(route, 1):
        y = top - (idx - 1) * row_h
        if idx % 2:
            panel(c, left, y, content, row_h, PAPER, radius=3)
        label(c, f"{idx:02d}", left + 10, y - 21, 9.3, TEAL, True)
        label(c, name, left + 41, y - 21, 9.1, TEXT)
        entry = headings[ordinal]
        page = entry["page"] + 1
        link(c, f"Mục #{ordinal}", SOURCE + "#" + entry["sectionId"], left + 326, y - 21, 8.4)
        link(c, f"PDF tr. {page}", SOURCE_PDF + f"#page={page}", left + 417, y - 21, 8.4)

    label(c, "Chỉ mục đầy đủ / 61 mục", left, 261, 13.2, INK, True)
    label(c, "Số thứ tự tính theo các câu hỏi trong bài, không phải số trang.", left, 244, 8.4, MUTED)
    top = 229
    for key, title, _ in priorities:
        numbers = [f"#{e['ordinal']}" for e in headings.values() if e["priority"] == key]
        c.setFillColor(PALETTE[key])
        c.roundRect(left, top - 14, 17, 14, 3, stroke=0, fill=1)
        label(c, title.replace(" / ", " · "), left + 25, top - 11, 8.5, TEXT, True)
        end = para(c, " &nbsp; ".join(numbers), left + 130, top + 1,
                   content - 130, size=8.2, leading=14)
        top = min(top - 37, end - 10)

    label(c, "Màu biểu thị ưu tiên đọc; nội dung gốc giữ nguyên.", left, 79, 8.3, MUTED)
    footer(c, 1, width)
    c.showPage()


def page_two(c):
    width, height = A4
    left, content = 42, width - 84
    label(c, "CÁCH SỬ DỤNG", left, height - 44, 8.3, TEAL, True)
    label(c, "Tạo bản đọc có highlight", left, height - 82, 23, INK, True)
    para(c, "Mở <b>hamel-evals-reading-kit.html</b> bằng trình duyệt.",
         left, 744, content, size=10, leading=15)

    panel(c, left, 711, content, 139)
    label(c, "01 / PDF · Giữ bố cục của tác giả", left + 14, 689, 11.1, INK, True)
    para(c, "1. Tải PDF gốc qua liên kết bên dưới.<br/>"
         "2. Trong bộ đọc, chọn <b>Chọn PDF gốc</b> và mở file vừa tải.<br/>"
         "3. Bấm <b>Tạo PDF đã highlight</b> để lưu bản đã được đánh dấu.",
         left + 14, 675, content - 28, size=9.3, leading=16)
    para(c, "Kết quả: <b>61 trang</b>, <b>61 nhãn ưu tiên</b> và <b>93 đoạn highlight</b>.<br/>"
         "Chế độ PDF chạy cục bộ, ngoại tuyến sau khi đã có file nguồn.",
         left + 14, 617, content - 28, size=8.7, leading=13, color=MUTED)
    link(c, "Tải PDF gốc từ tác giả", SOURCE_PDF, left + 14, 580, 8.7, True)

    panel(c, left, 558, content, 142)
    label(c, "02 / HTML · Đọc trong giao diện web", left + 14, 536, 11.1, INK, True)
    para(c, "1. Mở bài gốc, lưu file HTML, rồi chọn <b>Chọn HTML gốc</b>.<br/>"
         "2. Bấm <b>Mở bản highlight</b> để xem trước.<br/>"
         "3. Trên thanh công cụ, chọn <b>Lưu HTML</b> hoặc <b>In / lưu PDF</b>.",
         left + 14, 522, content - 28, size=9.3, leading=16)
    para(c, "CSS, font và hình gốc có thể cần mạng cho đến khi được nhúng "
         "hoặc lưu kèm đầy đủ. Khi in, bật đồ họa nền để giữ màu highlight.",
         left + 14, 464, content - 28, size=8.7, leading=13, color=MUTED)
    link(c, "Mở trang nguồn trên hamel.dev", SOURCE, left + 14, 424, 8.7, True)

    label(c, "Đối chiếu phiên bản trước khi đánh dấu", left, 392, 12.3, INK, True)
    top = 375
    items = [
        "<b>PDF:</b> đối chiếu SHA-256 với bản đã khảo sát. Nếu file khác hoặc nguồn đã "
        "thay đổi, công cụ dừng và không tạo PDF đánh dấu.",
        "<b>HTML:</b> kiểm tra từng mục; các mục không khớp được bỏ qua để tránh tô sai vị trí.",
        "<b>Nguồn:</b> gói này không chứa toàn văn hay PDF gốc. Bạn lấy nguồn trực tiếp "
        "từ tác giả qua các liên kết ở trên.",
    ]
    for text in items:
        c.setFillColor(TEAL)
        c.circle(left + 3, top - 6, 1.7, stroke=0, fill=1)
        top = para(c, text, left + 14, top, content - 14, size=9, leading=13.5) - 9

    label(c, "Tùy chọn dòng lệnh", left, 248, 12.3, INK, True)
    label(c, "Chạy từ thư mục gói, nơi có tools/ và data/:", left, 230, 8.8, MUTED)
    panel(c, left, 215, content, 57, fill=colors.HexColor("#EAF1F2"))
    label(c, "python -m pip install PyMuPDF", left + 12, 195, size=8.2, color=INK)
    label(c, "python tools/annotate_pdf.py --download -o private/evals-faq.highlighted.pdf",
          left + 12, 175, size=8.2, color=INK)
    para(c, "Lệnh tải nguồn cần kết nối mạng. File kết quả nằm trong <b>private/</b>; "
         "giữ bản nguồn và bản đã đánh dấu trong thư mục cá nhân.",
         left, 143, content, size=8.5, leading=13, color=MUTED)

    label(c, "Liên kết nguồn", left, 99, 8.4, MUTED, True)
    link(c, "hamel.dev/blog/posts/evals-faq/", SOURCE, left, 82, 8.1)
    link(c, "hamel.dev/blog/posts/evals-faq/evals-faq.pdf", SOURCE_PDF, left, 65, 8.1)
    footer(c, 2, width)
    c.showPage()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-dir", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "hamel-evals-reading-guide.pdf")
    args = parser.parse_args()
    register_fonts(args.font_dir)
    manifest = json.loads((ROOT / "data/pdf-annotations.json").read_text(encoding="utf-8"))
    headings = {
        entry["ordinal"]: entry for entry in manifest["entries"]
        if entry["kind"] == "heading"
    }
    if set(headings) != set(range(1, 62)):
        raise SystemExit("Expected one heading for each of the 61 FAQ sections")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(args.output), pagesize=A4, pageCompression=1, invariant=1)
    c.setTitle("Evals FAQ - Bản đồ đọc và hướng dẫn highlight")
    c.setAuthor("Reading guide; source article by Hamel Husain and Shreya Shankar")
    c.setSubject("Source-free navigation and instructions for the Evals FAQ reading kit")
    c.setCreator("Reading kit / ReportLab")
    page_one(c, manifest, headings)
    page_two(c)
    c.save()
    print(args.output.resolve())


if __name__ == "__main__":
    main()
