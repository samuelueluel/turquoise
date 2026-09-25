from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

try:
    import fitz
except ImportError as exc:
    raise unittest.SkipTest(f"PDF fixture dependency unavailable: {exc}") from exc


QUALITY_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "files/system/usr/share/turquoise/zotero-mcp-sidecar-quality.py"
)
_spec = importlib.util.spec_from_file_location("sidecar_quality_under_test", QUALITY_SOURCE)
quality = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(quality)


class _Reader:
    def __init__(self, pdf: Path, attachment_key: str = "ATTACH01") -> None:
        self.pdf = pdf
        self.attachment_key = attachment_key

    def get_attachment_paths(self, _item_key: str) -> list[dict[str, str]]:
        return [{
            "key": self.attachment_key,
            "content_type": "application/pdf",
            "resolved_path": str(self.pdf),
        }]


class SidecarQualityTests(unittest.TestCase):
    def test_math_minus_is_normalized(self) -> None:
        self.assertEqual(quality._number_tokens("−.059; \x15.430"), [("0.059", -1), ("0.43", -1)])

    def test_table_checker_detects_sign_disagreement_and_pdf_mismatch(self) -> None:
        source = (
            "TABLE 4. Coefficients\n"
            "<table><tr><td>VARIABLE</td><td>Coefficient</td><td>t-Statistic</td></tr>"
            "<tr><td>1993</td><td>.059</td><td>-3.453</td></tr></table>"
        )
        table = quality._extract_tables(source)[0]
        findings: list[dict[str, object]] = []
        result = quality._check_table(table, "1993 -.059 -3.453", findings)
        codes = {finding["code"] for finding in findings}
        self.assertEqual(result["coefficient_tstat_sign_disagreements"], 1)
        self.assertEqual(result["page_sign_mismatches"], 1)
        self.assertIn("coefficient_tstat_sign_disagreement", codes)
        self.assertIn("page_matched_numeric_sign_mismatch", codes)

    def test_multiple_values_in_a_table_cell_are_critical(self) -> None:
        source = (
            "TABLE 2\n<table><tr><td>Name</td><td>Value</td></tr>"
            "<tr><td>One</td><td>31.5 10.8</td></tr></table>"
        )
        findings: list[dict[str, object]] = []
        quality._check_table(quality._extract_tables(source)[0], None, findings)
        self.assertIn("multiple_numeric_values_in_cell", {f["code"] for f in findings})

    def _current_report_fixture(
        self, root: Path
    ) -> tuple[dict[str, object], _Reader, Path, Path, Path, Path]:
        item_key = "TESTITEM"
        sidecar_dir = root / "sidecars"
        work_dir = root / "work"
        sidecar_dir.mkdir()
        sidecar_path = sidecar_dir / f"{item_key}.md"
        sidecar_path.write_text("verified test sidecar\n", encoding="utf-8")
        pdf = root / "source.pdf"
        pdf_doc = fitz.open()
        page = pdf_doc.new_page()
        page.insert_text((50, 50), "test PDF text")
        pdf_doc.save(pdf)
        pdf_doc.close()

        manifest_dir = work_dir / item_key / "runs" / "run-test"
        manifest_dir.mkdir(parents=True)
        raw_markdown = manifest_dir / "raw.md"
        raw_markdown.write_text("raw MinerU output\n", encoding="utf-8")
        content_list = manifest_dir / "content_list.json"
        content_list.write_text(
            json.dumps([{"type": "text", "page_idx": 0, "text": "test"}]),
            encoding="utf-8",
        )
        manifest = manifest_dir / "manifest.json"
        manifest.write_text(json.dumps({
            "parser_version": "magic-pdf 1.3.12",
            "pdf_sha256": quality.sha256_file(pdf),
            "raw_markdown_path": str(raw_markdown),
            "raw_markdown_sha256": quality.sha256_file(raw_markdown),
            "content_list_path": str(content_list),
            "content_list_sha256": quality.sha256_file(content_list),
        }), encoding="utf-8")
        cfg: dict[str, object] = {"sidecar_dir": str(sidecar_dir), "work_dir": str(work_dir)}
        reader = _Reader(pdf)
        report = {
            "report_schema": quality.REPORT_SCHEMA,
            "check_version": quality.CHECK_VERSION,
            "item_key": item_key,
            "status": "eligible",
            "attachment_key": reader.attachment_key,
            "sidecar_sha256": quality.sha256_file(sidecar_path),
            "pdf_sha256": quality.sha256_file(pdf),
            "parser": {
                "version": "magic-pdf 1.3.12",
                "manifest_path": str(manifest),
                "manifest_sha256": quality.sha256_file(manifest),
                "raw_markdown_path": str(raw_markdown),
                "raw_markdown_sha256": quality.sha256_file(raw_markdown),
                "raw_markdown_sha256_actual": quality.sha256_file(raw_markdown),
            },
            "content_list": {
                "sha256": quality.sha256_file(content_list),
                "manifest_sha256": quality.sha256_file(content_list),
            },
        }
        quality.write_quality_report(report, cfg)
        return cfg, reader, sidecar_path, manifest, raw_markdown, content_list

    def test_current_report_passes_then_sidecar_edit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg, reader, sidecar_path, *_ = self._current_report_fixture(Path(tmp))
            verified = quality.verify_current_report("TESTITEM", cfg, reader)
            self.assertEqual(verified["status"], "eligible")
            sidecar_path.write_text("edited after check\n", encoding="utf-8")
            with self.assertRaisesRegex(quality.SidecarQualityError, "stale after a sidecar change"):
                quality.verify_current_report("TESTITEM", cfg, reader)

    def test_changed_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg, reader, _sidecar_path, manifest, *_ = self._current_report_fixture(Path(tmp))
            manifest.write_text(manifest.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(quality.SidecarQualityError, "manifest changed"):
                quality.verify_current_report("TESTITEM", cfg, reader)

    def test_report_stays_pinned_to_old_run_after_rejected_reparse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg, reader, _sidecar, old_manifest, *_ = self._current_report_fixture(Path(tmp))
            import time
            time.sleep(0.002)
            new_run = old_manifest.parent.parent / "rejected-run"
            new_run.mkdir()
            (new_run / "manifest.json").write_text(old_manifest.read_text(encoding="utf-8"))
            # The attempted run was never published; it must not invalidate a
            # prior eligible report or turn old chunks into a deletion target.
            self.assertEqual(quality.verify_current_report("TESTITEM", cfg, reader)["status"], "eligible")

    def test_changed_pdf_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg, reader, *_ = self._current_report_fixture(Path(tmp))
            reader.pdf.write_bytes(b"replacement PDF")
            with self.assertRaisesRegex(quality.SidecarQualityError, "stale after a PDF change"):
                quality.verify_current_report("TESTITEM", cfg, reader)

    def test_raw_markdown_changed_after_report_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg, reader, _sidecar, _manifest, raw_markdown, _content_list = self._current_report_fixture(Path(tmp))
            raw_markdown.write_text("mutated raw parse\n", encoding="utf-8")
            with self.assertRaisesRegex(quality.SidecarQualityError, "raw Markdown artifact changed"):
                quality.verify_current_report("TESTITEM", cfg, reader)

    def test_content_list_changed_after_report_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg, reader, _sidecar, _manifest, _raw_markdown, content_list = self._current_report_fixture(Path(tmp))
            content_list.write_text(json.dumps([{"type": "text", "page_idx": 0, "text": "changed"}]), encoding="utf-8")
            with self.assertRaisesRegex(quality.SidecarQualityError, "does not match its run manifest"):
                quality.verify_current_report("TESTITEM", cfg, reader)

    def test_missing_raw_markdown_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg, reader, _sidecar, _manifest, raw_markdown, _content_list = self._current_report_fixture(Path(tmp))
            raw_markdown.unlink()
            with self.assertRaisesRegex(quality.SidecarQualityError, "raw Markdown artifact is unavailable"):
                quality.verify_current_report("TESTITEM", cfg, reader)

    def test_missing_content_list_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg, reader, _sidecar, _manifest, _raw_markdown, content_list = self._current_report_fixture(Path(tmp))
            content_list.unlink()
            with self.assertRaisesRegex(quality.SidecarQualityError, "page-indexed MinerU source is unavailable"):
                quality.verify_current_report("TESTITEM", cfg, reader)

    def test_artifact_changed_before_report_creation_remains_review_required(self) -> None:
        for artifact in ("raw", "content"):
            with self.subTest(artifact=artifact), tempfile.TemporaryDirectory() as tmp:
                cfg, reader, _sidecar, _manifest, raw_markdown, content_list = self._current_report_fixture(Path(tmp))
                if artifact == "raw":
                    raw_markdown.write_text("changed before check\n", encoding="utf-8")
                    expected_code = "raw_markdown_hash_mismatch"
                else:
                    content_list.write_text("[]", encoding="utf-8")
                    expected_code = "content_list_hash_mismatch"
                report = quality.build_quality_report("TESTITEM", cfg, reader)
                codes = {finding["code"] for finding in report["findings"]}
                self.assertEqual(report["status"], "review_required")
                self.assertIn(expected_code, codes)

    def test_missing_report_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"sidecar_dir": str(Path(tmp) / "sidecars"), "work_dir": str(Path(tmp) / "work")}
            with self.assertRaisesRegex(quality.SidecarQualityError, "report missing"):
                quality.verify_current_report("TESTITEM", cfg, _Reader(Path(tmp) / "unused.pdf"))

    def test_failed_report_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg, reader, *_ = self._current_report_fixture(Path(tmp))
            path = quality.quality_report_path(cfg, "TESTITEM")
            report = json.loads(path.read_text(encoding="utf-8"))
            report["status"] = "failed"
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(quality.SidecarQualityError, "not eligible"):
                quality.verify_current_report("TESTITEM", cfg, reader)

    def test_review_required_report_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg, reader, *_ = self._current_report_fixture(Path(tmp))
            path = quality.quality_report_path(cfg, "TESTITEM")
            report = json.loads(path.read_text(encoding="utf-8"))
            report["status"] = "review_required"
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(quality.SidecarQualityError, "not eligible"):
                quality.verify_current_report("TESTITEM", cfg, reader)


if __name__ == "__main__":
    unittest.main()
