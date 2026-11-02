#!/usr/bin/env python3
"""Bundle the source-free reader. Python standard library only."""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def js_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

def build():
    html_manifest = json.loads((ROOT / "data/html-annotations.json").read_text())
    pdf_manifest = json.loads((ROOT / "data/pdf-annotations.json").read_text())
    labels = {7: "Phân tích lỗi", 10: "Chọn dữ liệu", 26: "Kiểm định judge", 56: "RAG", 61: "Agent", 49: "CI / production"}
    html_manifest["readingRoute"] = [
        {"id": next(s["id"] for s in html_manifest["sections"] if s["ordinal"] == n), "label": f"#{n:02d} {label}"}
        for n, label in labels.items()
    ]
    route_links = "".join(
        f'<a target="_blank" rel="noopener noreferrer" href="{html_manifest["sourceUrl"]}#{item["id"]}">{escape(item["label"])}</a>'
        for item in html_manifest["readingRoute"]
    )
    values = {
        "__ROUTE_LINKS__": route_links,
        "__PDF_LIB__": (ROOT / "vendor/pdf-lib.min.js").read_text().replace("</script", "<\\/script"),
        "__HTML_MANIFEST__": js_json(html_manifest),
        "__PDF_MANIFEST__": js_json(pdf_manifest),
        "__ANNOTATOR_JS_STRING__": js_json((ROOT / "tools/annotator.js").read_text()),
        "__READER_CSS_STRING__": js_json((ROOT / "tools/reader.css").read_text()),
    }
    output = (ROOT / "tools/reader-template.html").read_text()
    for key, value in values.items():
        output = output.replace(key, value)
    target = ROOT / "hamel-evals-reading-kit.html"
    target.write_text(output, encoding="utf-8")
    print(f"Built {target.name}: {target.stat().st_size:,} bytes")

if __name__ == "__main__":
    build()
