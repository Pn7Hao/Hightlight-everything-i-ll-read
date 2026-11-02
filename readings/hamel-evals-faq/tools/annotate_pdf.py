#!/usr/bin/env python3
"""Apply a coordinate-only reading overlay to the matching original PDF.

Install: python -m pip install PyMuPDF

Examples:
    python tools/annotate_pdf.py ~/Downloads/source.pdf -o private/reading.pdf
    python tools/annotate_pdf.py --download -o private/reading.pdf

The original article is not bundled. --download fetches it directly from the
publisher into the output directory. A SHA-256 pin prevents misplaced highlights
if the publisher changes the source. Keep generated copies in your private files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import urllib.error
import urllib.request


DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "data" / "pdf-annotations.json"
PRIORITIES = {
    "deep": {"label": "P1 | Read closely", "rgb": (1.0, 0.82, 0.12)},
    "skim": {"label": "P2 | Skim", "rgb": (0.22, 0.73, 0.52)},
    "reference": {"label": "P3 | Reference", "rgb": (0.50, 0.60, 0.83)},
}


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_source(path: Path, manifest: dict) -> None:
    actual = sha256_file(path)
    if actual != manifest["sha256"]:
        raise ValueError(
            "Source PDF has changed or is not the expected edition. "
            "No highlighted PDF was written.\n"
            f"Expected SHA-256: {manifest['sha256']}\n"
            f"Actual SHA-256:   {actual}\n"
            "Obtain the matching original or regenerate the coordinate manifest "
            "for the new edition; do not disable this check."
        )


def load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = manifest.get("sha256", "")
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("Manifest contains an invalid SHA-256 pin.")
    page_count = manifest.get("pageCount")
    dimensions = manifest.get("pageDimensions", [])
    if not isinstance(page_count, int) or page_count <= 0 or len(dimensions) != page_count:
        raise ValueError("Manifest page dimensions do not match its page count.")
    for width, height in dimensions:
        if width <= 0 or height <= 0:
            raise ValueError("Manifest contains invalid page dimensions.")
    for entry in manifest.get("entries", []):
        if entry.get("priority") not in PRIORITIES:
            raise ValueError("Manifest contains an unknown priority.")
        if entry.get("kind") not in {"heading", "highlight"}:
            raise ValueError("Manifest contains an unknown overlay kind.")
        page = entry.get("page")
        if not isinstance(page, int) or not 0 <= page < page_count:
            raise ValueError("Manifest contains an out-of-range page number.")
        width, height = dimensions[page]
        if not entry.get("rects"):
            raise ValueError("Manifest entry has no rectangles.")
        for rect in entry["rects"]:
            if len(rect) != 4 or not all(math.isfinite(v) for v in rect):
                raise ValueError("Manifest contains an invalid rectangle.")
            x0, y0, x1, y1 = rect
            if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
                raise ValueError("Manifest rectangle falls outside its page.")
    if not manifest.get("entries"):
        raise ValueError("Manifest has no annotations.")
    return manifest


def download_original(manifest: dict, path: Path) -> Path:
    if path.exists():
        verify_source(path, manifest)
        return path
    request = urllib.request.Request(
        manifest["sourceUrl"], headers={"User-Agent": "personal-reading-overlay/1.0"}
    )
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".source-download-", suffix=".pdf", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            with urllib.request.urlopen(request, timeout=60) as response:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    handle.write(chunk)
        verify_source(temporary, manifest)
        temporary.replace(path)
        return path
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def annotate(source: Path, output: Path, manifest: dict) -> dict:
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required. Install it with: python -m pip install PyMuPDF"
        ) from exc

    verify_source(source, manifest)
    temporary = None
    try:
        with pymupdf.open(source) as document:
            if document.needs_pass:
                raise ValueError("The source PDF requires a password.")
            if len(document) != manifest["pageCount"]:
                raise ValueError("Source page count does not match the coordinate manifest.")
            original_toc = document.get_toc()
            original_text = [page.get_text() for page in document]
            for index, page in enumerate(document):
                expected_width, expected_height = manifest["pageDimensions"][index]
                if (
                    abs(page.rect.width - expected_width) > 0.01
                    or abs(page.rect.height - expected_height) > 0.01
                ):
                    raise ValueError(f"Unexpected dimensions on page {index + 1}.")

            counts = {"heading": 0, "highlight": 0}
            for entry in manifest["entries"]:
                page = document[entry["page"]]
                style = PRIORITIES[entry["priority"]]
                rectangles = [pymupdf.Rect(r) for r in entry["rects"]]
                if entry["kind"] == "heading":
                    # A small margin bar keeps priority distinct from text emphasis.
                    left = min(rect.x0 for rect in rectangles)
                    top = min(rect.y0 for rect in rectangles)
                    bottom = max(rect.y1 for rect in rectangles)
                    bar = pymupdf.Rect(max(2, left - 8), top, max(5, left - 4), bottom)
                    annotation = page.add_rect_annot(bar)
                    annotation.set_colors(stroke=style["rgb"], fill=style["rgb"])
                    annotation.set_border(width=0)
                    annotation.set_opacity(0.90)
                else:
                    annotation = page.add_highlight_annot(rectangles)
                    annotation.set_colors(stroke=style["rgb"])
                    annotation.set_opacity(0.30)
                annotation.set_info(
                    title=f"Reading guide | FAQ {entry['ordinal']:02d}",
                    subject=style["label"],
                    content=f"FAQ {entry['ordinal']:02d} - {style['label']}",
                )
                annotation.update()
                counts[entry["kind"]] += 1

            with tempfile.NamedTemporaryFile(
                prefix=".annotated-", suffix=".pdf", dir=output.parent, delete=False
            ) as handle:
                temporary = Path(handle.name)
            document.save(temporary, garbage=3, deflate=True)

        # Verify that the overlay preserves all article text and bookmarks.
        with pymupdf.open(temporary) as check:
            if check.get_toc() != original_toc:
                raise RuntimeError("Bookmark verification failed; output was not published.")
            if [page.get_text() for page in check] != original_text:
                raise RuntimeError("Text verification failed; output was not published.")
        temporary.replace(output)
        return counts
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, nargs="?", help="Original PDF obtained from the publisher")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Private output PDF path")
    parser.add_argument("--download", action="store_true", help="Download the original from the publisher into the output directory")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Coordinate manifest path")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing annotated output (never the source)")
    args = parser.parse_args()
    if bool(args.input) == args.download:
        parser.error("Specify exactly one original PDF path or --download.")

    try:
        manifest = load_manifest(args.manifest)
        output = args.output.expanduser().resolve()
        if output.suffix.lower() != ".pdf":
            raise ValueError("Output path must end in .pdf.")
        if output.exists() and not args.overwrite:
            raise ValueError("Output already exists. Choose another path or pass --overwrite.")
        output.parent.mkdir(parents=True, exist_ok=True)
        if args.download:
            source = download_original(manifest, output.with_name(output.stem + ".original.pdf"))
        else:
            source = args.input.expanduser().resolve()
        if source == output:
            raise ValueError("The output must be different from the original PDF.")
        counts = annotate(source, output, manifest)
        print(f"Created: {output}")
        print(f"Preserved {manifest['pageCount']} pages, article text, and bookmarks.")
        print(f"Added {counts['highlight']} highlights and {counts['heading']} FAQ priority markers.")
        print("Colors: gold = P1 Read closely; green = P2 Skim; muted purple = P3 Reference.")
        return 0
    except (ValueError, OSError, RuntimeError, urllib.error.URLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
