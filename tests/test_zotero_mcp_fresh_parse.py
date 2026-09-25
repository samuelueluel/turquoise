from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import fitz
    from zotero_mcp import mineru, semantic_search, sidecar_quality as quality
except ImportError as exc:
    raise unittest.SkipTest(f"installed Zotero package unavailable: {exc}") from exc


class _Reader:
    def __init__(self, pdf: Path):
        self.pdf = pdf

    def get_attachment_paths(self, _key: str):
        return [{"key": "ATTACH01", "content_type": "application/pdf", "resolved_path": str(self.pdf)}]


class FreshParseTests(unittest.TestCase):
    def test_fresh_parse_gets_report_while_legacy_and_unknown_stay_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sidecars, work = root / "sidecars", root / "work"
            sidecars.mkdir()
            work.mkdir()
            pdf = root / "source.pdf"
            doc = fitz.open()
            doc.new_page().insert_text((50, 50), "source text")
            doc.save(pdf)
            doc.close()
            cfg = {"enabled": True, "sidecar_dir": str(sidecars), "work_dir": str(work)}
            reader = _Reader(pdf)

            def read_sidecar(_cfg, key):
                path = sidecars / f"{key}.md"
                return path.read_text() if path.is_file() else None

            def parse(key, _reader):
                version = "magic-pdf==1.3.12" if key == "FRESH001" else None
                text = "fresh generated source text\n"
                (sidecars / f"{key}.md").write_text(text)
                run = work / key / "runs" / "run-one"
                run.mkdir(parents=True)
                raw = run / "raw.md"
                raw.write_text(text)
                content = run / "content_list.json"
                content.write_text(json.dumps([{"type": "text", "page_idx": 0, "text": "source text"}]))
                (run / "manifest.json").write_text(json.dumps({
                    "item_key": key, "attachment_key": "ATTACH01",
                    "pdf_sha256": quality.sha256_file(pdf),
                    "parser_version": version,
                    "raw_markdown_path": str(raw), "raw_markdown_sha256": quality.sha256_file(raw),
                    "content_list_path": str(content), "content_list_sha256": quality.sha256_file(content),
                }))
                return text, "mineru"

            with patch.object(mineru, "load_mineru_config", return_value=cfg), \
                 patch.object(mineru, "read_sidecar", side_effect=read_sidecar), \
                 patch.object(mineru, "try_auto_parse", side_effect=parse):
                result = list(semantic_search._extract_fulltext_batch(reader, [(1, "FRESH001")]))
                self.assertEqual(result, [(1, ("fresh generated source text\n", "mineru"))])
                self.assertEqual(json.loads((sidecars / "FRESH001.quality.json").read_text())["status"], "eligible")
                with self.assertRaises(quality.SidecarQualityError):
                    list(semantic_search._extract_fulltext_batch(reader, [(2, "FRESH002")]))
                self.assertEqual(json.loads((sidecars / "FRESH002.quality.json").read_text())["status"], "review_required")
                (sidecars / "LEGACY01.md").write_text("existing manual sidecar\n")
                with self.assertRaisesRegex(quality.SidecarQualityError, "report missing"):
                    list(semantic_search._extract_fulltext_batch(reader, [(3, "LEGACY01")]))
                self.assertFalse((sidecars / "LEGACY01.quality.json").exists())


if __name__ == "__main__":
    unittest.main()
