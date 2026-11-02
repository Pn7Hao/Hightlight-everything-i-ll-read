"""Standard-library regression tests for the reading-kit bundler."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


BUILD_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "readings/hamel-evals-faq/tools/build_kit.py"
)
spec = importlib.util.spec_from_file_location("build_kit", BUILD_SCRIPT)
build_kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_kit)


class BuildKitEncodingTests(unittest.TestCase):
    def test_utf8_inputs_are_independent_of_legacy_default_encoding(self):
        """Simulate Windows cp1252 defaults without needing a Windows host."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures = {
                "data/html-annotations.json": json.dumps({
                    "sourceUrl": "https://example.test/article/",
                    "title": "Đọc kỹ",
                    "sections": [
                        {"ordinal": ordinal, "id": f"section-{ordinal}"}
                        for ordinal in (7, 10, 26, 56, 61, 49)
                    ],
                }, ensure_ascii=False),
                "data/pdf-annotations.json": '{"title":"Đọc kỹ"}',
                "vendor/purify.min.js": "/* Đọc kỹ */",
                "vendor/pdf-lib.min.js": "/* Đọc kỹ */",
                "tools/annotator.js": 'const label = "Đọc kỹ";',
                "tools/reader.css": "/* Đọc kỹ */",
                "tools/reader-template.html": (
                    "<!doctype html><title>Đọc kỹ</title>"
                    "__ROUTE_LINKS__ __PDF_LIB__ __HTML_MANIFEST__ "
                    "__PDF_MANIFEST__ __ANNOTATOR_JS_STRING__ __READER_CSS_STRING__"
                ),
            }
            for name, content in fixtures.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            original_read_text = Path.read_text
            reads = []

            def legacy_read_text(path, encoding=None, errors=None, **kwargs):
                reads.append((path.relative_to(root), encoding))
                return original_read_text(
                    path, encoding=encoding or "cp1252", errors=errors, **kwargs
                )

            with patch.object(build_kit, "ROOT", root), patch.object(
                Path, "read_text", legacy_read_text
            ):
                build_kit.build()

            self.assertEqual(len(reads), len(fixtures))
            self.assertTrue(all(encoding == "utf-8" for _, encoding in reads))
            output = (root / "hamel-evals-reading-kit.html").read_text(encoding="utf-8")
            self.assertIn("Đọc kỹ", output)
            self.assertIn("Phân tích lỗi", output)
            for placeholder in ("__HTML_MANIFEST__", "__PDF_MANIFEST__", "__READER_CSS_STRING__"):
                self.assertNotIn(placeholder, output)


if __name__ == "__main__":
    unittest.main()
