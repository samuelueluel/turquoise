from __future__ import annotations

from contextlib import ExitStack
import importlib.util
import os
import json
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

try:
    import chromadb
    from chromadb.config import Settings
    import fitz
    from zotero_mcp.chroma_client import _NoEmbeddingFunction
except ImportError as exc:
    raise unittest.SkipTest(f"installed Zotero test dependencies unavailable: {exc}") from exc

HOME = Path.home()
QUALITY = HOME / "turquoise/files/system/usr/share/turquoise/zotero-mcp-sidecar-quality.py"
RUNNER = HOME / ".local/bin/zotero-sidecar-reprocess.py"
CREATOR = HOME / ".local/bin/zotero-sidecar-create.py"
VLM = HOME / ".local/bin/zotero-vlm-enrich.py"
WATCHER = HOME / ".local/bin/zotero-sidecar-batch-watch.py"
if not all(path.is_file() for path in (QUALITY, RUNNER, CREATOR, VLM, WATCHER)):
    raise unittest.SkipTest("live Chezmoi-managed Zotero pipeline scripts are unavailable")


def module_at(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


quality = module_at("batch_test_quality", QUALITY)
runner = module_at("batch_test_runner", RUNNER)
watcher = module_at("batch_test_watcher", WATCHER)


class FakeReader:
    def __init__(self, pdf: Path):
        self.pdf = pdf

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def resolve_collection_keys(self, _key: str):
        return []

    def get_attachment_paths(self, _key: str):
        return [{"key": "ATTACH01", "content_type": "application/pdf", "resolved_path": str(self.pdf)}]


class ReprocessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pdf = self.root / "source.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "test text")
        doc.save(self.pdf)
        doc.close()
        self.reader = FakeReader(self.pdf)
        self.live_cfg = {
            "enabled": True,
            "sidecar_dir": str(self.root / "live-sidecars"),
            "work_dir": str(self.root / "live-work"),
        }
        self.live_sidecar = Path(self.live_cfg["sidecar_dir"]) / "TESTITEM.md"
        self.live_sidecar.parent.mkdir()
        self.live_sidecar.write_text("previously indexed source\n", encoding="utf-8")
        self.run_dir = self.root / "batch"
        self.cfg_path = self.root / "config.json"
        self.cfg_path.write_text(json.dumps({"semantic_search": {
            "zotero_db_path": "isolated-test", "collection_name": "batch_isolated_test",
        }}))
        db_dir = self.root / ".config/zotero-mcp/chroma_db"
        db_dir.mkdir(parents=True)
        client = chromadb.PersistentClient(
            path=str(db_dir), settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )
        self.collection = client.get_or_create_collection(
            "batch_isolated_test", embedding_function=_NoEmbeddingFunction()
        )
        self.collection.upsert(
            ids=["TESTITEM#0"], documents=["previously indexed source"],
            metadatas=[{"item_key": "TESTITEM"}], embeddings=[[0.1, 0.2, 0.3]],
        )
        self.index_cli = self.root / "fake-index-cli"
        self.index_cli.write_text("#!/bin/sh\nprintf '%s\\n' '- Processed: 1'\n")
        self.index_cli.chmod(0o755)

    def fake_index(self, succeed: bool):
        def run(_cmd, *, stdout, **_kwargs):
            self.collection.delete(ids=["TESTITEM#0"])
            if succeed:
                self.collection.upsert(
                    ids=["TESTITEM#0"], documents=["fresh parsed source"],
                    metadatas=[{"item_key": "TESTITEM"}], embeddings=[[0.4, 0.5, 0.6]],
                )
                stdout.write("- Processed: 1\n")
                stdout.flush()
            return SimpleNamespace(returncode=0 if succeed else 7)
        return run

    def fake_parse(self, parser_version: str | None):
        def parse(cfg, _pdf, key, *, attachment_key):
            work = Path(cfg["work_dir"]) / key / "runs" / "run-isolated-test"
            raw = work / "out" / "paper" / "txt" / "paper.md"
            raw.parent.mkdir(parents=True)
            raw.write_text("fresh parsed source\n", encoding="utf-8")
            content = raw.with_name("paper_content_list.json")
            content.write_text(json.dumps([{"type": "text", "page_idx": 0, "text": "test text"}]))
            sidecar = Path(cfg["sidecar_dir"]) / f"{key}.md"
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_bytes(raw.read_bytes())
            manifest = {
                "item_key": key, "attachment_key": attachment_key,
                "parser_version": parser_version, "pdf_sha256": quality.sha256_file(self.pdf),
                "raw_markdown_path": str(raw), "raw_markdown_sha256": quality.sha256_file(raw),
                "content_list_path": str(content), "content_list_sha256": quality.sha256_file(content),
            }
            (work / "manifest.json").write_text(json.dumps(manifest))
            return True
        return parse

    def runner_patches(self, parser_version: str | None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(runner, "quality", quality))
        stack.enter_context(patch.object(runner, "HOME", self.root))
        stack.enter_context(patch.object(runner, "CONFIG", self.cfg_path))
        stack.enter_context(patch.object(runner, "INDEX_CLI", self.index_cli))
        stack.enter_context(patch.object(runner, "LocalZoteroReader", return_value=self.reader))
        stack.enter_context(patch.object(runner.mineru, "load_mineru_config", return_value=self.live_cfg))
        stack.enter_context(patch.object(runner.mineru, "run_mineru", side_effect=self.fake_parse(parser_version)))
        return stack

    def test_staged_success_publishes_and_indexes_exact_item(self):
        self.runner_patches("magic-pdf==1.3.12")
        with patch.object(runner.subprocess, "run", side_effect=self.fake_index(True)):
            code = runner.run_batch(["TESTITEM"], self.run_dir, enrich=False)
        self.assertEqual(code, 0)
        self.assertEqual(self.live_sidecar.read_text(), "fresh parsed source\n")
        self.assertEqual((self.run_dir / "backups/TESTITEM/sidecar.before.md").read_text(), "previously indexed source\n")
        self.assertEqual(quality.verify_current_report("TESTITEM", self.live_cfg, self.reader)["status"], "eligible")
        manifest = Path(self.live_cfg["work_dir"]) / "TESTITEM/runs/run-isolated-test/manifest.json"
        self.assertTrue(manifest.is_file())
        self.assertTrue(Path(json.loads(manifest.read_text())["raw_markdown_path"]).is_file())
        self.assertEqual(json.loads((self.run_dir / "state/TESTITEM.json").read_text())["status"], "indexed")
        self.assertEqual(self.collection.get(ids=["TESTITEM#0"], include=["documents"])["documents"], ["fresh parsed source"])
        # Resume must not parse or re-embed a successfully verified item.
        with patch.object(runner.subprocess, "run", side_effect=AssertionError("resumed a successful item")):
            self.assertEqual(runner.run_batch(["TESTITEM"], self.run_dir, enrich=False), 0)

    def test_approved_table_transfer_is_pdf_bound_and_fails_closed(self):
        raw_table = "<table><tr><td>1.5</td></tr></table>"
        fixed_table = "<table><tr><td>-1.5</td></tr></table>"
        staged_home = self.run_dir / "staging/TESTITEM"
        staged = staged_home / ".config/zotero-mcp/mineru-sidecars/TESTITEM.md"
        staged.parent.mkdir(parents=True)
        staged.write_text("source\n" + raw_table + "\n")
        self.live_sidecar.write_text("reviewed\n" + fixed_table + "\n")
        old_report = {
            "item_key": "TESTITEM", "status": "review_required",
            "pdf_sha256": quality.sha256_file(self.pdf),
            "sidecar_sha256": quality.sha256_file(self.live_sidecar),
        }
        quality.quality_report_path(self.live_cfg, "TESTITEM").write_text(json.dumps(old_report))
        mapping = {runner._table_digest(raw_table): runner._table_digest(fixed_table)}
        protection = {"pdf_sha256": quality.sha256_file(self.pdf), "raw_to_corrected": mapping}
        with patch.dict(runner.REVIEWED_TABLE_EDITS, {"TESTITEM": protection}):
            runner.transfer_reviewed_tables("TESTITEM", self.pdf, self.live_cfg, staged_home, staged)
            self.assertIn(fixed_table, staged.read_text())
            self.assertNotIn(raw_table, staged.read_text())
            record = json.loads((staged_home / "approved-table-transfer.json").read_text())
            self.assertEqual(record["transferred"], 1)
            staged.write_text("source\n<table><tr><td>unknown</td></tr></table>\n")
            with self.assertRaisesRegex(RuntimeError, "fresh table differs"):
                runner.transfer_reviewed_tables("TESTITEM", self.pdf, self.live_cfg, staged_home, staged)
            self.assertIn(fixed_table, self.live_sidecar.read_text())
            staged.write_text("source\n" + raw_table + "\n")
            self.pdf.write_bytes(self.pdf.read_bytes() + b"changed after approval")
            with self.assertRaisesRegex(RuntimeError, "source/report/PDF changed"):
                runner.transfer_reviewed_tables("TESTITEM", self.pdf, self.live_cfg, staged_home, staged)
            self.assertIn(raw_table, staged.read_text())

    def test_ambiguous_pdfs_require_a_frozen_pin_through_publication_and_indexing(self):
        self.runner_patches("magic-pdf==1.3.12")
        other_pdf = self.root / "appendix.pdf"
        other_pdf.write_bytes(self.pdf.read_bytes() + b"different attached PDF")

        def attachments(_key):
            return [
                {"key": "ATTACH01", "content_type": "application/pdf", "resolved_path": str(self.pdf)},
                {"key": "ATTACH02", "content_type": "application/pdf", "resolved_path": str(other_pdf)},
            ]
        with patch.object(self.reader, "get_attachment_paths", side_effect=attachments), \
             patch.object(runner.subprocess, "run", side_effect=self.fake_index(True)):
            self.assertEqual(runner.run_batch(["TESTITEM"], self.run_dir / "unpinned", enrich=False), 1)
            self.assertEqual(self.live_sidecar.read_text(), "previously indexed source\n")
            self.assertEqual(json.loads((self.run_dir / "unpinned/state/TESTITEM.json").read_text())["status"], "blocked")
            self.assertEqual(runner.run_batch(
                ["TESTITEM"], self.run_dir / "pinned", enrich=False,
                attachments={"TESTITEM": "ATTACH01"},
            ), 0)
            report = quality.verify_current_report("TESTITEM", self.live_cfg, self.reader)
            self.assertEqual(report["attachment_key"], "ATTACH01")
            self.assertEqual(json.loads((self.run_dir / "pinned/state/TESTITEM.json").read_text())["status"], "indexed")

    def test_explicit_orphan_exclusion_is_reported_and_frozen_before_execution(self):
        self.runner_patches("magic-pdf==1.3.12")
        (self.live_sidecar.parent / "OTHERKEY.md").write_text("orphan sidecar\n")
        with patch("sys.stdout") as output:
            self.assertEqual(runner.main([
                "--existing-sidecars", "--exclude-key", "OTHERKEY",
                "--attachment", "TESTITEM=ATTACH01",
            ]), 0)
            text = " ".join(str(call.args) for call in output.write.call_args_list)
            self.assertIn("1 of 2 sidecars: OTHERKEY", text)
        with patch.object(runner, "local_embedder_ready"), \
             patch.object(runner, "local_vlm_ready"), \
             patch.object(runner, "run_batch", return_value=0) as batch:
            self.assertEqual(runner.main([
                "--existing-sidecars", "--exclude-key", "OTHERKEY",
                "--attachment", "TESTITEM=ATTACH01", "--run-dir", str(self.run_dir),
                "--execute", "--confirm-live-reembed", "REEMBED",
            ]), 0)
        self.assertEqual(batch.call_args.args, (["TESTITEM"], self.run_dir))
        self.assertEqual(batch.call_args.kwargs["attachments"], {"TESTITEM": "ATTACH01"})
        scope = json.loads((self.run_dir / "scope.json").read_text())
        self.assertEqual(scope["source_sidecars"], 2)
        self.assertEqual(scope["excluded_keys"], ["OTHERKEY"])
        self.assertEqual(scope["keys"], ["TESTITEM"])
        identity = json.loads((self.run_dir / "runner-pid.json").read_text())
        self.assertEqual(identity["pid"], os.getpid())
        self.assertEqual(identity["start_ticks"], runner.process_start_ticks(os.getpid()))
        self.assertEqual(identity["run_dir"], str(self.run_dir))
        with self.assertRaises(SystemExit) as caught:
            runner.main(["--resume", "--run-dir", str(self.run_dir), "--exclude-key", "OTHERKEY"])
        self.assertEqual(caught.exception.code, 2)

    def test_batch_watchdog_validates_runner_birth_and_exact_scope(self):
        record = {"pid": 9876, "start_ticks": 12345, "runner": str(RUNNER), "run_dir": str(self.run_dir)}
        argv = ["python", str(RUNNER), "--run-dir", str(self.run_dir), "--execute"]
        with patch.object(watcher, "process_info", return_value=(1, 12345)), \
             patch.object(watcher, "cmdline", return_value=argv):
            self.assertTrue(watcher.runner_alive(self.run_dir, record))
            self.assertFalse(watcher.runner_alive(self.run_dir / "another", record))
            self.assertFalse(watcher.runner_alive(self.run_dir, {**record, "start_ticks": 999}))
        with patch.object(watcher, "process_info", return_value=(1, 12345)), \
             patch.object(watcher, "cmdline", return_value=["python", "unrelated", "--run-dir", str(self.run_dir)]):
            self.assertFalse(watcher.runner_alive(self.run_dir, record))

    def test_batch_watchdog_targets_only_a_pinned_runner_child(self):
        sleep_bin = shutil.which('sleep')
        if not sleep_bin:
            self.skipTest('sleep not available for scoped process test')
        target = subprocess.Popen([sleep_bin, '30'])
        unrelated = subprocess.Popen([sleep_bin, '30'])
        try:
            own_children = watcher.parser_children(os.getpid(), sleep_bin)
            self.assertIn(target.pid, own_children)
            self.assertIn(unrelated.pid, own_children)
            self.assertEqual(watcher.parser_children(os.getpid() + 999999, sleep_bin), [])
            self.assertEqual(watcher.stop_parser(target.pid, os.getpid() + 999999), 0)
            self.assertIsNone(target.poll())
            self.assertEqual(watcher.stop_parser(target.pid, os.getpid()), 1)
            target.wait(timeout=5)
            self.assertIsNone(unrelated.poll())
        finally:
            for proc in (target, unrelated):
                if proc.poll() is None:
                    proc.terminate()
                proc.wait(timeout=5)

    def test_orphan_sidecar_without_a_linked_pdf_stays_blocked(self):
        self.runner_patches("magic-pdf==1.3.12")
        with patch.object(self.reader, "get_attachment_paths", return_value=[]), \
             patch.object(runner.mineru, "run_mineru", side_effect=AssertionError("parsed an orphan")), \
             patch.object(runner.subprocess, "run", side_effect=AssertionError("indexed an orphan")):
            self.assertEqual(runner.run_batch(["TESTITEM"], self.run_dir, enrich=False), 1)
        self.assertEqual(self.live_sidecar.read_text(), "previously indexed source\n")
        self.assertEqual(self.collection.get(ids=["TESTITEM#0"], include=["documents"])["documents"], ["previously indexed source"])
        self.assertEqual(json.loads((self.run_dir / "state/TESTITEM.json").read_text())["status"], "blocked")

    def test_attachment_pins_are_scoped_and_immutable_on_resume(self):
        with patch("sys.stdout"):
            self.assertEqual(runner.main(["--key", "TESTITEM", "--attachment", "TESTITEM=ATTACH01"]), 0)
        for args in (
            ["--key", "TESTITEM", "--attachment", "OTHERKEY=ATTACH01"],
            ["--key", "TESTITEM", "--attachment", "TESTITEM=ATTACH01", "--attachment", "TESTITEM=ATTACH02"],
        ):
            with self.assertRaises(SystemExit) as caught:
                runner.main(args)
            self.assertEqual(caught.exception.code, 2)
        runner.save_json(self.run_dir / "scope.json", {
            "keys": ["TESTITEM"], "attachments": {"TESTITEM": "ATTACH01"}, "enrich": True,
        })
        with self.assertRaises(SystemExit) as caught:
            runner.main(["--resume", "--run-dir", str(self.run_dir), "--attachment", "TESTITEM=ATTACH02"])
        self.assertEqual(caught.exception.code, 2)

    def test_blocked_parse_keeps_old_sidecar_and_never_invokes_index(self):
        self.runner_patches(None)
        self.index_cli.write_text("#!/bin/sh\necho INDEXED > '" + str(self.root / "index-called") + "'\n")
        self.assertEqual(runner.run_batch(["TESTITEM"], self.run_dir, enrich=False), 1)
        self.assertEqual(self.live_sidecar.read_text(), "previously indexed source\n")
        self.assertFalse((self.root / "index-called").exists())
        self.assertEqual(json.loads((self.run_dir / "state/TESTITEM.json").read_text())["status"], "blocked")
        self.assertTrue((self.run_dir / "staging/TESTITEM/.config/zotero-mcp/mineru-sidecars/TESTITEM.quality.json").is_file())

    def test_index_failure_restores_original_chunks_and_can_resume(self):
        self.runner_patches("magic-pdf==1.3.12")
        with patch.object(runner.subprocess, "run", side_effect=self.fake_index(False)):
            self.assertEqual(runner.run_batch(["TESTITEM"], self.run_dir, enrich=False), 1)
        self.assertEqual(json.loads((self.run_dir / "state/TESTITEM.json").read_text())["status"], "index_failed")
        self.assertEqual(json.loads((self.run_dir / "summary.json").read_text())["incomplete"], True)
        self.assertEqual(self.collection.get(ids=["TESTITEM#0"], include=["documents"])["documents"], ["previously indexed source"])
        with patch.object(runner.subprocess, "run", side_effect=self.fake_index(True)):
            self.assertEqual(runner.run_batch(["TESTITEM"], self.run_dir, enrich=False), 0)
        self.assertEqual(json.loads((self.run_dir / "state/TESTITEM.json").read_text())["status"], "indexed")

    def test_restore_failure_stops_batch_for_manual_index_recovery(self):
        self.runner_patches("magic-pdf==1.3.12")
        with patch.object(runner.subprocess, "run", side_effect=self.fake_index(False)), \
             patch.object(runner, "restore_snapshot", side_effect=RuntimeError("restore failed")):
            self.assertEqual(runner.run_batch(["TESTITEM", "NEXTITEM"], self.run_dir, enrich=False), 1)
        self.assertEqual(json.loads((self.run_dir / "state/TESTITEM.json").read_text())["status"], "recovery_required")
        self.assertFalse((self.run_dir / "state/NEXTITEM.json").exists())

    def test_vlm_outage_stops_batch_without_publishing_or_indexing(self):
        self.runner_patches("magic-pdf==1.3.12")
        original = self.fake_parse("magic-pdf==1.3.12")

        def parse_with_image(cfg, pdf, key, *, attachment_key):
            original(cfg, pdf, key, attachment_key=attachment_key)
            path = Path(cfg["sidecar_dir"]) / f"{key}.md"
            path.write_text(path.read_text() + "![](images/crop.png)\n")
            return True

        with patch.object(runner.mineru, "run_mineru", side_effect=parse_with_image), \
             patch.object(runner, "local_vlm_ready", side_effect=runner.ServiceUnavailable("VLM stopped")):
            self.assertEqual(runner.run_batch(["TESTITEM", "NEXTITEM"], self.run_dir, enrich=True), 1)
        status = json.loads((self.run_dir / "state/TESTITEM.json").read_text())
        self.assertEqual(status["status"], "service_unavailable")
        self.assertFalse((self.run_dir / "state/NEXTITEM.json").exists())
        self.assertEqual(self.live_sidecar.read_text(), "previously indexed source\n")
        self.assertEqual(self.collection.get(ids=["TESTITEM#0"], include=["documents"])["documents"], ["previously indexed source"])

    def test_interrupted_index_restores_saved_chunks_before_retry(self):
        self.runner_patches("magic-pdf==1.3.12")
        stage_home = self.run_dir / "staging/TESTITEM"
        runner.prepare_item("TESTITEM", self.reader, self.live_cfg, stage_home, enrich=False)
        runner.publish_item("TESTITEM", self.reader, self.live_cfg, stage_home, self.run_dir / "backups/TESTITEM")
        runner.index_snapshot("TESTITEM", self.run_dir / "snapshots/TESTITEM.json")
        runner.save_json(self.run_dir / "state/TESTITEM.json", {"status": "indexing", "item_key": "TESTITEM"})
        self.collection.delete(ids=["TESTITEM#0"])
        # A crashed CLI left the indexed paper with no chunks. Resume must
        # restore the old record before making the next exact-key attempt.
        def retry(_cmd, *, stdout, **_kwargs):
            self.assertEqual(
                self.collection.get(where={"item_key": "TESTITEM"}, include=["documents"])["documents"],
                ["previously indexed source"],
            )
            return self.fake_index(True)(_cmd, stdout=stdout)
        with patch.object(runner.subprocess, "run", side_effect=retry):
            self.assertEqual(runner.run_batch(["TESTITEM"], self.run_dir, enrich=False), 0)
        self.assertEqual(self.collection.get(ids=["TESTITEM#0"], include=["documents"])["documents"], ["fresh parsed source"])

    def test_live_execute_refuses_unpatched_package_before_writes(self):
        with patch.object(runner.quality, "_parser_manifest", lambda cfg, key, pdf_hash: None):
            with self.assertRaises(SystemExit) as caught:
                runner.main([
                    "--key", "TESTITEM", "--run-dir", str(self.run_dir),
                    "--execute", "--confirm-live-reembed", "REEMBED",
                ])
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(self.run_dir.exists())

    def test_unavailable_local_embedder_refuses_before_live_writes(self):
        self.runner_patches("magic-pdf==1.3.12")
        self.cfg_path.write_text(json.dumps({"semantic_search": {
            "zotero_db_path": "isolated-test", "embedding_config": {"base_url": "http://127.0.0.1:9/v1"},
        }}))
        with self.assertRaises(SystemExit) as caught:
            runner.main([
                "--key", "TESTITEM", "--run-dir", str(self.run_dir),
                "--execute", "--confirm-live-reembed", "REEMBED",
            ])
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse(self.run_dir.exists())

    def test_split_stage_create_generates_report_after_new_parse(self):
        creator = module_at("batch_test_creator", CREATOR)
        sidecar = Path(self.live_cfg["sidecar_dir"]) / "TESTITEM.md"
        sidecar.unlink()
        with ExitStack() as stack:
            stack.enter_context(patch.object(creator, "CFG_PATH", self.cfg_path))
            stack.enter_context(patch.object(creator, "LOG", self.root / "create.log"))
            stack.enter_context(patch.object(creator, "ensure_ocr_flag_patch", return_value="already-patched"))
            stack.enter_context(patch.object(creator, "LocalZoteroReader", return_value=self.reader))
            stack.enter_context(patch.object(creator.mineru, "load_mineru_config", return_value={**self.live_cfg, "bin": "fake-mineru"}))
            stack.enter_context(patch.object(creator.mineru, "read_sidecar", return_value=None))
            stack.enter_context(patch.object(creator.mineru, "run_mineru", side_effect=self.fake_parse("magic-pdf==1.3.12")))
            stack.enter_context(patch.object(creator.sidecar_quality, "build_quality_report", quality.build_quality_report))
            stack.enter_context(patch.object(creator.sidecar_quality, "write_quality_report", quality.write_quality_report))
            stack.enter_context(patch("sys.argv", ["zotero-sidecar-create.py", "TESTITEM"]))
            creator.main()
        report = json.loads((sidecar.parent / "TESTITEM.quality.json").read_text())
        self.assertEqual(report["status"], "eligible")
        self.assertIn("CHECKED TESTITEM: eligible", (self.root / "create.log").read_text())

    def test_figure_enrichment_runs_on_staged_source_before_index(self):
        self.runner_patches("magic-pdf==1.3.12")
        staged = self.run_dir / "staging/TESTITEM"
        raw = staged / ".cache/zotero-mcp/mineru-work/TESTITEM/runs/run-isolated-test/out/paper/txt/paper.md"
        sidecar = staged / ".config/zotero-mcp/mineru-sidecars/TESTITEM.md"
        image_ref = "fresh parsed source\n![](images/crop.png)\n"
        original_parse = self.fake_parse("magic-pdf==1.3.12")

        def parse_with_image(cfg, pdf, key, *, attachment_key):
            original_parse(cfg, pdf, key, attachment_key=attachment_key)
            raw.write_text(image_ref)
            sidecar.write_text(image_ref)
            image = raw.parent / "images/crop.png"
            image.parent.mkdir()
            image.write_bytes(b"fake crop")
            content = raw.with_name("paper_content_list.json")
            content.write_text(json.dumps([
                {"type": "text", "page_idx": 0, "text": "test text"},
                {"type": "image", "page_idx": 0, "img_path": "images/crop.png"},
            ]))
            manifest_path = raw.parents[3] / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["raw_markdown_sha256"] = quality.sha256_file(raw)
            manifest["content_list_sha256"] = quality.sha256_file(content)
            manifest_path.write_text(json.dumps(manifest))
            return True

        def dispatch(cmd, *, stdout, env, **kwargs):
            if str(runner.ENRICH_CLI) in cmd:
                self.assertEqual(Path(env["HOME"]), staged)
                self.assertEqual(env["ZOTERO_VLM_URL"], "http://127.0.0.1:18085/v1/chat/completions")
                sidecar.write_text(image_ref + "[Figure Schema]\n- Type: plot\n")
                stdout.write("staged image enriched\n")
                stdout.flush()
                return SimpleNamespace(returncode=0)
            return self.fake_index(True)(cmd, stdout=stdout)

        with patch.object(runner.mineru, "run_mineru", side_effect=parse_with_image), \
             patch.object(runner, "local_vlm_ready", return_value=None), \
             patch.dict(os.environ, {"ZOTERO_VLM_URL": "http://127.0.0.1:18085/v1/chat/completions"}), \
             patch.object(runner.subprocess, "run", side_effect=dispatch):
            self.assertEqual(runner.run_batch(["TESTITEM"], self.run_dir, enrich=True), 0)
        self.assertIn("[Figure Schema]", self.live_sidecar.read_text())
        self.assertEqual(quality.verify_current_report("TESTITEM", self.live_cfg, self.reader)["status"], "eligible")

    def test_pipeline_defaults_to_dedicated_vlm_and_rejects_nonloopback(self):
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(runner, "urlopen", return_value=Response()) as opened:
            runner.local_vlm_ready()
            self.assertEqual(opened.call_args.args[0], "http://127.0.0.1:18084/v1/models")
        for invalid in ("https://example.org/v1/chat/completions",
                        "http://127.0.0.1:18084/v1/chat/completions?unsafe=1",
                        "http://127.0.0.1/v1/chat/completions"):
            with self.subTest(endpoint=invalid), patch.dict(os.environ, {"ZOTERO_VLM_URL": invalid}):
                with self.assertRaises(runner.ServiceUnavailable):
                    runner.local_vlm_ready()

    def test_temporary_vlm_endpoint_is_local_and_uses_models_preflight(self):
        target = "http://127.0.0.1:18085/v1/chat/completions"
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
        with patch.dict(os.environ, {"ZOTERO_VLM_URL": target}), \
             patch.object(runner, "urlopen", return_value=Response()) as opened:
            runner.local_vlm_ready()
            self.assertEqual(opened.call_args.args[0], "http://127.0.0.1:18085/v1/models")
            vlm = module_at("batch_test_vlm_endpoint", VLM)
            self.assertEqual(vlm.VLM_URL, target)
        with patch.dict(os.environ, {"ZOTERO_VLM_URL": "https://example.org/v1/chat/completions"}):
            with self.assertRaises(runner.ServiceUnavailable):
                runner.local_vlm_ready()

    def test_vlm_cli_returns_failure_when_image_request_drops(self):
        vlm = module_at("batch_test_vlm_errors", VLM)
        with patch.object(vlm.requests, "get", return_value=SimpleNamespace(status_code=200)), \
             patch.object(vlm, "process_sidecar", return_value={
                 "figures": 1, "schema": 0, "already": 0, "restamp": 0,
                 "dim_filter": 0, "missing_img": 0, "vlm_err": 1,
                 "caption": 0, "caption_skip": 0, "caption_none": 0,
             }), \
             patch("sys.argv", ["zotero-vlm-enrich.py", "--key", "TESTITEM"]):
            self.assertEqual(vlm.main(), 1)

    def test_new_style_run_images_are_locatable_for_enrichment(self):
        vlm = module_at("batch_test_vlm", VLM)
        work = self.root / "staged-work"
        image_dir = work / "TESTITEM/runs/run-one/out/paper/txt/images"
        image_dir.mkdir(parents=True)
        (image_dir / "crop.png").write_bytes(b"fake")
        (work / "TESTITEM/runs/run-one/manifest.json").write_text("{}")
        vlm.WORK_DIR = work
        self.assertEqual(vlm.resolve_image("TESTITEM", "images/crop.png"), image_dir / "crop.png")

    def test_enrichment_never_falls_back_to_legacy_images_after_reparse(self):
        vlm = module_at("batch_test_vlm_no_fallback", VLM)
        work = self.root / "staged-work"
        legacy = work / "TESTITEM/out/old/txt/images"
        legacy.mkdir(parents=True)
        (legacy / "crop.png").write_bytes(b"outdated figure")
        current = work / "TESTITEM/runs/run-new"
        current.mkdir(parents=True)
        (current / "manifest.json").write_text("{}")
        vlm.WORK_DIR = work
        self.assertIsNone(vlm.resolve_image("TESTITEM", "images/crop.png"))


if __name__ == "__main__":
    unittest.main()
